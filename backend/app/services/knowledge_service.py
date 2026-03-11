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


class KnowledgeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedder = EmbeddingProvider()
        self.llm_service = LLMService()
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

        # Populate tsvector via SQL (handles Chinese via 'simple' config)
        if created_ids:
            await db.execute(
                text(
                    "UPDATE knowledge_point "
                    "SET search_vector = to_tsvector('simple', "
                    "  coalesce(title,'') || ' ' || coalesce(content,'') "
                    "  || ' ' || coalesce(array_to_string(tags,' '),'')) "
                    "WHERE id = ANY(:ids)"
                ),
                {"ids": created_ids},
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
        stmt = text(
            "SELECT id, title, content, answer, subject, category, "
            "       difficulty, tags, source_company, "
            "       ts_rank(search_vector, plainto_tsquery('simple', :query)) AS rank "
            "FROM knowledge_point "
            "WHERE search_vector @@ plainto_tsquery('simple', :query) "
            "ORDER BY rank DESC "
            "LIMIT :top_k"
        )
        result = await db.execute(stmt, {"query": query, "top_k": top_k})
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

    @staticmethod
    def _rerank(results: list[dict], query: str) -> list[dict]:
        """Simulated bge-reranker-large reranking.

        Combines vector similarity and keyword relevance with title/tag bonuses.
        Replace with a real cross-encoder model when available.
        """
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

        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return results

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
