"""Knowledge ingestion, hybrid search, and RAG Q&A service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.knowledge_bookmark import KnowledgeBookmark
from app.models.knowledge_category import KnowledgeCategory
from app.models.knowledge_learning_progress import KnowledgeLearningProgress, LearningStatus
from app.models.knowledge_point import DifficultyLevel, KnowledgePoint, KnowledgePointType
from app.models.position_knowledge import PositionKnowledge
from app.providers.embedding import EmbeddingProvider
from app.providers.llm_factory import LLMService
from app.providers.reranker import RerankerProvider
from app.utils.prompt_manager import PromptManager
from app.utils.text_splitter import (
    RecursiveTextSplitter,
    extract_text_from_file,
    segment_chinese,
    split_markdown_sections,
)


class KnowledgeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedder = EmbeddingProvider()
        self.llm_service = LLMService()
        self.reranker = RerankerProvider()
        self.prompt_manager = PromptManager()
        self._rag_prompt = self._load_rag_prompt()

    # ── RAG prompt ─────────────────────────────────────────
    def _load_rag_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "rag_qa.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8").strip()
        return (
            "你是专业的校招面试官助手。请仅基于以下提供的参考资料回答用户的问题。"
            "如果资料中没有答案，请直接告知用户无法回答，不要编造。"
        )

    # ── 1. Ingestion ───────────────────────────────────────
    async def ingest_cards(
        self,
        db: AsyncSession,
        cards: list[dict],
        *,
        owner_user_id: int | None = None,
        category_id: int | None = None,
    ) -> list[int]:
        """Vectorise knowledge cards and save to database."""
        if not cards:
            raise AppException("no cards provided", code=3001)

        # Prepare texts for embedding
        texts_for_embedding: list[str] = []
        for card in cards:
            parts = [card.get("title", ""), card.get("content", "")]
            if card.get("answer"):
                parts.append(card["answer"])
            texts_for_embedding.append("\n".join(parts))

        embeddings = self.embedder.embed_batch(texts_for_embedding)

        created_ids: list[int] = []
        for card, embedding in zip(cards, embeddings):
            kp = KnowledgePoint(
                subject=card.get("subject", "Computer Science"),
                category=card.get("category", "General"),
                type=KnowledgePointType(card.get("type", "KNOWLEDGE")),
                difficulty=DifficultyLevel(card.get("difficulty", "MEDIUM")),
                title=card.get("title", "Untitled"),
                content=card.get("content", ""),
                answer=card.get("answer"),
                source_company=card.get("source_company"),
                tags=card.get("tags", []),
                category_id=category_id,
                owner_user_id=owner_user_id,
                embedding=embedding,
            )
            db.add(kp)
            await db.flush()
            created_ids.append(kp.id)

        # Populate tsvector with jieba-segmented text for Chinese FTS
        if created_ids:
            for kp_id, card in zip(created_ids, cards):
                raw = (
                    f"{card.get('title', '')} {card.get('content', '')} "
                    f"{' '.join(card.get('tags', []))}"
                )
                segmented = segment_chinese(raw)
                await db.execute(
                    text(
                        "UPDATE knowledge_point "
                        "SET search_vector = to_tsvector('simple', :seg_text) "
                        "WHERE id = :kp_id"
                    ),
                    {"seg_text": segmented, "kp_id": kp_id},
                )

        await db.commit()
        return created_ids

    # ── 2. Hybrid search ──────────────────────────────────
    async def hybrid_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 10,
        *,
        scope: str | None = None,
        visibility: str = "PUBLIC",
        user_id: int | None = None,
    ) -> list[dict]:
        """Dual-path retrieval (vector + keyword), merge, rerank, return top-k."""
        query_embedding = self.embedder.embed(query)

        vector_results = await self._vector_search(
            db,
            query_embedding,
            top_k,
            scope=scope,
            visibility=visibility,
            user_id=user_id,
        )
        keyword_results = await self._keyword_search(
            db,
            query,
            top_k,
            scope=scope,
            visibility=visibility,
            user_id=user_id,
        )

        merged = self._merge_results(vector_results, keyword_results)
        reranked = self._rerank(merged, query)
        return reranked[:top_k]

    async def _vector_search(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        top_k: int,
        *,
        scope: str | None,
        visibility: str,
        user_id: int | None,
    ) -> list[dict]:
        filters, params = self._build_visibility_filters(visibility=visibility, user_id=user_id)
        if scope:
            filters.append("scope = :scope")
            params["scope"] = scope
        filter_sql = " AND ".join(filters)

        stmt = text(
            "SELECT id, title, content, answer, subject, category, "
            "       difficulty, tags, source_company, "
            "       embedding <=> :q ::vector AS distance "
            "FROM knowledge_point "
            f"WHERE {filter_sql} "
            "ORDER BY distance ASC "
            "LIMIT :top_k"
        )
        params.update({"q": str(query_embedding), "top_k": top_k})
        result = await db.execute(stmt, params)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "content": r["content"],
                "answer": r["answer"],
                "subject": r["subject"],
                "category": r["category"],
                "difficulty": r["difficulty"],
                "tags": r["tags"],
                "source_company": r["source_company"],
                "score": 1.0 - float(r["distance"]),
                "source": "vector",
            }
            for r in result.mappings().all()
        ]

    async def _keyword_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int,
        *,
        scope: str | None,
        visibility: str,
        user_id: int | None,
    ) -> list[dict]:
        filters, params = self._build_visibility_filters(visibility=visibility, user_id=user_id)
        if scope:
            filters.append("scope = :scope")
            params["scope"] = scope
        filter_sql = " AND ".join(filters)

        segmented_query = segment_chinese(query)
        stmt = text(
            "SELECT id, title, content, answer, subject, category, "
            "       difficulty, tags, source_company, "
            "       ts_rank(search_vector, plainto_tsquery('simple', :query)) AS rank "
            "FROM knowledge_point "
            f"WHERE {filter_sql} AND search_vector @@ plainto_tsquery('simple', :query) "
            "ORDER BY rank DESC "
            "LIMIT :top_k"
        )
        params.update({"query": segmented_query, "top_k": top_k})
        result = await db.execute(stmt, params)
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "content": r["content"],
                "answer": r["answer"],
                "subject": r["subject"],
                "category": r["category"],
                "difficulty": r["difficulty"],
                "tags": r["tags"],
                "source_company": r["source_company"],
                "score": float(r["rank"]),
                "source": "keyword",
            }
            for r in result.mappings().all()
        ]

    # ── merge & rerank ────────────────────────────────────
    @staticmethod
    def _merge_results(
        vector_results: list[dict], keyword_results: list[dict]
    ) -> list[dict]:
        seen: dict[int, dict] = {}
        for item in vector_results:
            item["keyword_score"] = 0.0
            seen[item["id"]] = item
        for item in keyword_results:
            kid = item["id"]
            if kid in seen:
                seen[kid]["keyword_score"] = item["score"]
                seen[kid]["source"] = "both"
            else:
                item["keyword_score"] = item["score"]
                seen[kid] = item
        return list(seen.values())

    def _rerank(self, results: list[dict], query: str) -> list[dict]:
        """Rerank using DashScope gte-rerank, with weighted formula fallback."""
        if not results:
            return results

        # Try real cross-encoder reranker
        documents = [
            f"{item.get('title', '')} {item.get('content', '')}".strip()
            for item in results
        ]
        rerank_results = self.reranker.rerank(query, documents, top_n=len(results))

        if rerank_results:
            score_map = {r["index"]: r["relevance_score"] for r in rerank_results}
            for i, item in enumerate(results):
                item["rerank_score"] = score_map.get(i, 0.0)
        else:
            self._fallback_rerank(results, query)

        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return results

    @staticmethod
    def _fallback_rerank(results: list[dict], query: str) -> None:
        """Weighted scoring fallback when gte-rerank is unavailable."""
        query_lower = query.lower()
        for item in results:
            vector_score = item.get("score", 0.0) if item.get("source") != "keyword" else 0.0
            keyword_score = item.get("keyword_score", 0.0)

            title_bonus = 0.1 if query_lower in (item.get("title") or "").lower() else 0.0

            tag_bonus = 0.0
            for tag in item.get("tags") or []:
                if query_lower in tag.lower() or tag.lower() in query_lower:
                    tag_bonus = 0.05
                    break

            item["rerank_score"] = (
                0.7 * vector_score + 0.2 * min(keyword_score, 1.0) + title_bonus + tag_bonus
            )

    # ── 3. RAG Q&A chain ─────────────────────────────────
    async def ask_knowledge_base(self, db: AsyncSession, question: str) -> dict:
        """Retrieve relevant knowledge and generate a grounded answer."""
        if not question.strip():
            raise AppException("question cannot be empty", code=3002)

        search_results = await self.hybrid_search(db, question, top_k=10, visibility="PUBLIC")
        # Return top-3 after reranking (already sorted)
        top_results = search_results[:3]

        if not top_results:
            return {
                "answer": "抱歉，知识库中没有找到相关资料，无法回答该问题。",
                "references": [],
            }

        context_parts: list[str] = []
        references: list[dict] = []
        for i, item in enumerate(top_results, 1):
            references.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "subject": item["subject"],
                    "category": item["category"],
                }
            )
            ctx = f"【参考资料 {i}】\n标题: {item['title']}\n内容: {item['content']}"
            if item.get("answer"):
                ctx += f"\n参考答案: {item['answer']}"
            context_parts.append(ctx)

        context = "\n\n".join(context_parts)

        full_prompt = self.prompt_manager.render_with_fallback(
            "knowledge/rag_answer.md",
            (
                "{{ rag_system_prompt }}\n\n"
                "参考资料:\n{{ context }}\n\n"
                "用户问题: {{ question }}\n\n"
                "请基于以上参考资料回答:"
            ),
            rag_system_prompt=self._rag_prompt,
            context=context,
            question=question,
        )

        answer = self.llm_service.chat("RAG", full_prompt)
        return {"answer": answer, "references": references}

    # ── 4. Document upload & auto-chunking ────────────────
    async def ingest_document(
        self,
        db: AsyncSession,
        filename: str,
        content: bytes,
        subject: str = "Computer Science",
        category: str = "General",
        difficulty: str = "MEDIUM",
        owner_user_id: int | None = None,
        category_id: int | None = None,
    ) -> list[int]:
        """Extract text from a document, chunk it, embed, and store."""
        raw_text = extract_text_from_file(filename, content)
        if not raw_text.strip():
            raise AppException("document is empty or text extraction failed", code=3003)

        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        splitter = RecursiveTextSplitter(chunk_size=500, chunk_overlap=100)

        cards: list[dict] = []
        if suffix in ("md", "markdown"):
            cards = self._chunk_markdown(raw_text, filename, subject, category, difficulty, splitter)
        else:
            cards = self._chunk_plain(raw_text, filename, subject, category, difficulty, splitter)

        if not cards:
            raise AppException("no content chunks extracted from document", code=3004)

        return await self.ingest_cards(
            db,
            cards,
            owner_user_id=owner_user_id,
            category_id=category_id,
        )

    # ── 5. Category / point browsing ──────────────────────
    async def list_categories_tree(
        self,
        db: AsyncSession,
        *,
        subject: str,
        user_id: int,
        position_id: int | None = None,
    ) -> list[dict]:
        rows = await db.execute(
            select(KnowledgeCategory)
            .where(KnowledgeCategory.subject == subject, KnowledgeCategory.is_active.is_(True))
            .order_by(KnowledgeCategory.sort_order.asc(), KnowledgeCategory.id.asc())
        )
        categories = list(rows.scalars().all())
        if not categories:
            return []

        category_ids = [c.id for c in categories]
        point_stmt = (
            select(KnowledgePoint.id, KnowledgePoint.category_id)
            .where(
                KnowledgePoint.subject == subject,
                KnowledgePoint.category_id.in_(category_ids),
                or_(KnowledgePoint.owner_user_id.is_(None), KnowledgePoint.owner_user_id == user_id),
            )
        )
        if position_id is not None:
            point_stmt = point_stmt.join(
                PositionKnowledge,
                PositionKnowledge.knowledge_point_id == KnowledgePoint.id,
            ).where(PositionKnowledge.position_id == position_id)

        point_rows = (await db.execute(point_stmt)).all()
        point_ids = [row[0] for row in point_rows]

        count_map: dict[int, int] = {}
        for _, cat_id in point_rows:
            if cat_id is None:
                continue
            count_map[cat_id] = count_map.get(cat_id, 0) + 1

        read_map: dict[int, int] = {}
        if point_ids:
            read_rows = await db.execute(
                select(KnowledgePoint.category_id)
                .join(KnowledgeLearningProgress, KnowledgeLearningProgress.knowledge_point_id == KnowledgePoint.id)
                .where(
                    KnowledgeLearningProgress.user_id == user_id,
                    KnowledgeLearningProgress.status != LearningStatus.UNREAD,
                    KnowledgePoint.id.in_(point_ids),
                )
            )
            for cat_id in read_rows.scalars().all():
                if cat_id is None:
                    continue
                read_map[cat_id] = read_map.get(cat_id, 0) + 1

        nodes: dict[int, dict] = {
            c.id: {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "parent_id": c.parent_id,
                "subject": c.subject,
                "sort_order": c.sort_order,
                "point_count": count_map.get(c.id, 0),
                "read_count": read_map.get(c.id, 0),
                "children": [],
            }
            for c in categories
        }

        roots: list[dict] = []
        for c in categories:
            node = nodes[c.id]
            if c.parent_id and c.parent_id in nodes:
                nodes[c.parent_id]["children"].append(node)
            else:
                roots.append(node)

        def _sort_recursive(items: list[dict]) -> None:
            items.sort(key=lambda x: (x["sort_order"], x["id"]))
            for item in items:
                _sort_recursive(item["children"])

        _sort_recursive(roots)
        return roots

    async def list_points(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        category_id: int | None = None,
        position_id: int | None = None,
        difficulty: str | None = None,
        subject: str | None = None,
        include_private: bool = True,
    ) -> list[dict]:
        stmt = select(KnowledgePoint)
        filters = []
        if category_id is not None:
            filters.append(KnowledgePoint.category_id == category_id)
        if subject:
            filters.append(KnowledgePoint.subject == subject)
        if difficulty:
            filters.append(KnowledgePoint.difficulty == difficulty)
        if include_private:
            filters.append(or_(KnowledgePoint.owner_user_id.is_(None), KnowledgePoint.owner_user_id == user_id))
        else:
            filters.append(KnowledgePoint.owner_user_id.is_(None))

        if filters:
            stmt = stmt.where(and_(*filters))

        if position_id is not None:
            stmt = stmt.join(
                PositionKnowledge,
                PositionKnowledge.knowledge_point_id == KnowledgePoint.id,
            ).where(PositionKnowledge.position_id == position_id)

        stmt = stmt.order_by(KnowledgePoint.updated_at.desc(), KnowledgePoint.id.desc())
        points = list((await db.execute(stmt)).scalars().all())
        if not points:
            return []

        point_ids = [p.id for p in points]
        bookmark_ids = set(
            (await db.execute(
                select(KnowledgeBookmark.knowledge_point_id).where(
                    KnowledgeBookmark.user_id == user_id,
                    KnowledgeBookmark.knowledge_point_id.in_(point_ids),
                )
            )).scalars().all()
        )
        progress_rows = await db.execute(
            select(KnowledgeLearningProgress.knowledge_point_id, KnowledgeLearningProgress.status).where(
                KnowledgeLearningProgress.user_id == user_id,
                KnowledgeLearningProgress.knowledge_point_id.in_(point_ids),
            )
        )
        progress_map = {pid: status.value for pid, status in progress_rows.all()}

        return [
            {
                "id": p.id,
                "title": p.title,
                "subject": p.subject,
                "category": p.category,
                "difficulty": p.difficulty.value,
                "is_bookmarked": p.id in bookmark_ids,
                "learning_status": progress_map.get(p.id, LearningStatus.UNREAD.value),
                "is_owned_by_me": p.owner_user_id == user_id,
            }
            for p in points
        ]

    async def get_point_detail(self, db: AsyncSession, *, user_id: int, point_id: int) -> dict:
        point = (
            await db.execute(select(KnowledgePoint).where(KnowledgePoint.id == point_id))
        ).scalar_one_or_none()
        if point is None:
            raise AppException("knowledge point not found", code=3006)
        if point.owner_user_id is not None and point.owner_user_id != user_id:
            raise AppException("no permission to access this knowledge point", code=3007)

        bookmarked = (
            await db.execute(
                select(func.count(KnowledgeBookmark.id)).where(
                    KnowledgeBookmark.user_id == user_id,
                    KnowledgeBookmark.knowledge_point_id == point_id,
                )
            )
        ).scalar_one()
        progress = (
            await db.execute(
                select(KnowledgeLearningProgress).where(
                    KnowledgeLearningProgress.user_id == user_id,
                    KnowledgeLearningProgress.knowledge_point_id == point_id,
                )
            )
        ).scalar_one_or_none()

        related = (
            await db.execute(
                select(KnowledgePoint.id)
                .where(
                    KnowledgePoint.subject == point.subject,
                    KnowledgePoint.id != point.id,
                    KnowledgePoint.category == point.category,
                    or_(KnowledgePoint.owner_user_id.is_(None), KnowledgePoint.owner_user_id == user_id),
                )
                .order_by(KnowledgePoint.updated_at.desc())
                .limit(6)
            )
        ).scalars().all()

        return {
            "id": point.id,
            "title": point.title,
            "subject": point.subject,
            "category": point.category,
            "content": point.content,
            "answer": point.answer,
            "difficulty": point.difficulty.value,
            "tags": point.tags or [],
            "is_bookmarked": bool(bookmarked),
            "learning_status": progress.status.value if progress else LearningStatus.UNREAD.value,
            "is_owned_by_me": point.owner_user_id == user_id,
            "related_point_ids": list(related),
        }

    # ── 6. Bookmark / progress ───────────────────────────
    async def create_bookmark(self, db: AsyncSession, *, user_id: int, point_id: int) -> None:
        point = (
            await db.execute(select(KnowledgePoint).where(KnowledgePoint.id == point_id))
        ).scalar_one_or_none()
        if point is None:
            raise AppException("knowledge point not found", code=3006)
        if point.owner_user_id is not None and point.owner_user_id != user_id:
            raise AppException("no permission to bookmark this point", code=3007)

        existing = (
            await db.execute(
                select(KnowledgeBookmark).where(
                    KnowledgeBookmark.user_id == user_id,
                    KnowledgeBookmark.knowledge_point_id == point_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return

        db.add(KnowledgeBookmark(user_id=user_id, knowledge_point_id=point_id))
        await db.commit()

    async def remove_bookmark(self, db: AsyncSession, *, user_id: int, point_id: int) -> None:
        bookmark = (
            await db.execute(
                select(KnowledgeBookmark).where(
                    KnowledgeBookmark.user_id == user_id,
                    KnowledgeBookmark.knowledge_point_id == point_id,
                )
            )
        ).scalar_one_or_none()
        if bookmark is None:
            return
        await db.delete(bookmark)
        await db.commit()

    async def list_my_bookmarks(self, db: AsyncSession, *, user_id: int) -> list[dict]:
        rows = await db.execute(
            select(KnowledgeBookmark, KnowledgePoint)
            .join(KnowledgePoint, KnowledgePoint.id == KnowledgeBookmark.knowledge_point_id)
            .where(KnowledgeBookmark.user_id == user_id)
            .order_by(KnowledgeBookmark.created_at.desc())
        )
        items = []
        for bookmark, point in rows.all():
            items.append(
                {
                    "bookmark_id": bookmark.id,
                    "knowledge_point_id": point.id,
                    "title": point.title,
                    "subject": point.subject,
                    "category": point.category,
                    "created_at": bookmark.created_at,
                }
            )
        return items

    async def upsert_learning_progress(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        point_id: int,
        status: str,
        read_duration_seconds: float,
    ) -> dict:
        point = (
            await db.execute(select(KnowledgePoint).where(KnowledgePoint.id == point_id))
        ).scalar_one_or_none()
        if point is None:
            raise AppException("knowledge point not found", code=3006)
        if point.owner_user_id is not None and point.owner_user_id != user_id:
            raise AppException("no permission to update this point", code=3007)

        status_enum = self._to_learning_status(status)
        progress = (
            await db.execute(
                select(KnowledgeLearningProgress).where(
                    KnowledgeLearningProgress.user_id == user_id,
                    KnowledgeLearningProgress.knowledge_point_id == point_id,
                )
            )
        ).scalar_one_or_none()

        now = datetime.now(UTC)
        duration = max(0.0, float(read_duration_seconds or 0.0))
        if progress is None:
            progress = KnowledgeLearningProgress(
                user_id=user_id,
                knowledge_point_id=point_id,
                status=status_enum,
                read_duration_seconds=duration,
                last_read_at=now,
            )
            db.add(progress)
        else:
            progress.status = status_enum
            progress.read_duration_seconds = max(0.0, progress.read_duration_seconds + duration)
            progress.last_read_at = now

        await db.commit()
        await db.refresh(progress)
        return {
            "knowledge_point_id": point_id,
            "status": progress.status.value,
            "read_duration_seconds": progress.read_duration_seconds,
            "last_read_at": progress.last_read_at,
        }

    @staticmethod
    def _to_learning_status(status: str) -> LearningStatus:
        try:
            return LearningStatus((status or "UNREAD").upper())
        except Exception as exc:  # noqa: BLE001
            raise AppException("invalid learning status", code=3008) from exc

    @staticmethod
    def _build_visibility_filters(visibility: str, user_id: int | None) -> tuple[list[str], dict]:
        mode = (visibility or "PUBLIC").upper()
        if mode not in {"PUBLIC", "PRIVATE", "BOTH"}:
            mode = "PUBLIC"

        params: dict[str, object] = {}
        if mode == "PRIVATE":
            if user_id is None:
                return ["1 = 0"], params
            params["user_id"] = user_id
            return ["owner_user_id = :user_id"], params
        if mode == "BOTH":
            if user_id is None:
                return ["owner_user_id IS NULL"], params
            params["user_id"] = user_id
            return ["(owner_user_id IS NULL OR owner_user_id = :user_id)"], params
        return ["owner_user_id IS NULL"], params

    @staticmethod
    def _chunk_markdown(
        text: str,
        filename: str,
        subject: str,
        category: str,
        difficulty: str,
        splitter: RecursiveTextSplitter,
    ) -> list[dict]:
        sections = split_markdown_sections(text)
        cards: list[dict] = []
        for section in sections:
            section_title = section["title"] or filename
            section_content = section["content"]
            if not section_content.strip():
                continue
            if len(section_content) <= splitter.chunk_size:
                cards.append({
                    "subject": subject,
                    "category": category,
                    "type": "KNOWLEDGE",
                    "difficulty": difficulty,
                    "title": section_title,
                    "content": section_content,
                    "tags": [f"source:{filename}"],
                })
            else:
                chunks = splitter.split_text(section_content)
                for i, chunk in enumerate(chunks, 1):
                    cards.append({
                        "subject": subject,
                        "category": category,
                        "type": "KNOWLEDGE",
                        "difficulty": difficulty,
                        "title": f"{section_title} (part {i})",
                        "content": chunk,
                        "tags": [f"source:{filename}"],
                    })
        return cards

    @staticmethod
    def _chunk_plain(
        text: str,
        filename: str,
        subject: str,
        category: str,
        difficulty: str,
        splitter: RecursiveTextSplitter,
    ) -> list[dict]:
        chunks = splitter.split_text(text)
        cards: list[dict] = []
        for i, chunk in enumerate(chunks, 1):
            first_line = chunk.split("\n")[0][:100].strip()
            title = first_line if first_line else f"{filename} chunk {i}"
            cards.append({
                "subject": subject,
                "category": category,
                "type": "KNOWLEDGE",
                "difficulty": difficulty,
                "title": title,
                "content": chunk,
                "tags": [f"source:{filename}"],
            })
        return cards
