"""Knowledge ingestion, hybrid search, and RAG Q&A service."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.knowledge_point import DifficultyLevel, KnowledgePoint, KnowledgePointType
from app.providers.embedding import EmbeddingProvider
from app.providers.llm_factory import LLMService
from app.providers.reranker import RerankerProvider
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
    async def ingest_cards(self, db: AsyncSession, cards: list[dict]) -> list[int]:
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
        self, db: AsyncSession, query: str, top_k: int = 10
    ) -> list[dict]:
        """Dual-path retrieval (vector + keyword), merge, rerank, return top-k."""
        query_embedding = self.embedder.embed(query)

        vector_results = await self._vector_search(db, query_embedding, top_k)
        keyword_results = await self._keyword_search(db, query, top_k)

        merged = self._merge_results(vector_results, keyword_results)
        reranked = self._rerank(merged, query)
        return reranked[:top_k]

    async def _vector_search(
        self, db: AsyncSession, query_embedding: list[float], top_k: int
    ) -> list[dict]:
        stmt = text(
            "SELECT id, title, content, answer, subject, category, "
            "       difficulty, tags, source_company, "
            "       embedding <=> :q ::vector AS distance "
            "FROM knowledge_point "
            "WHERE embedding IS NOT NULL "
            "ORDER BY distance ASC "
            "LIMIT :top_k"
        )
        result = await db.execute(
            stmt, {"q": str(query_embedding), "top_k": top_k}
        )
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
        self, db: AsyncSession, query: str, top_k: int
    ) -> list[dict]:
        segmented_query = segment_chinese(query)
        stmt = text(
            "SELECT id, title, content, answer, subject, category, "
            "       difficulty, tags, source_company, "
            "       ts_rank(search_vector, plainto_tsquery('simple', :query)) AS rank "
            "FROM knowledge_point "
            "WHERE search_vector @@ plainto_tsquery('simple', :query) "
            "ORDER BY rank DESC "
            "LIMIT :top_k"
        )
        result = await db.execute(stmt, {"query": segmented_query, "top_k": top_k})
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

        search_results = await self.hybrid_search(db, question, top_k=10)
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

        full_prompt = (
            f"{self._rag_prompt}\n\n"
            f"参考资料:\n{context}\n\n"
            f"用户问题: {question}\n\n"
            f"请基于以上参考资料回答:"
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

        return await self.ingest_cards(db, cards)

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
