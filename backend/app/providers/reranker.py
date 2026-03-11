"""Reranker provider using DashScope gte-rerank API.

Falls back gracefully when the API key is missing or the call fails,
allowing the caller to use a weighted-formula fallback.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RerankerProvider:
    """Cross-encoder reranking via DashScope ``gte-rerank``."""

    MODEL = "gte-rerank"

    def __init__(self) -> None:
        self.settings = get_settings()

    def rerank(
        self, query: str, documents: list[str], top_n: int = 3
    ) -> list[dict] | None:
        """Rerank *documents* by relevance to *query*.

        Returns a list of ``{"index": int, "relevance_score": float}``
        sorted by score descending, or ``None`` when the service is
        unavailable so that the caller can apply a local fallback.
        """
        if not self.settings.dashscope_api_key or not documents:
            return None

        try:
            from dashscope import TextReRank

            resp = TextReRank.call(
                model=self.MODEL,
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
                return_documents=False,
                api_key=self.settings.dashscope_api_key,
            )

            if not hasattr(resp, "output") or resp.output is None:
                logger.warning("reranker returned empty output: %s", resp)
                return None

            results = resp.output.get("results", [])
            return [
                {
                    "index": r["index"],
                    "relevance_score": float(r["relevance_score"]),
                }
                for r in results
            ]
        except Exception:
            logger.warning("reranker call failed, falling back to weighted scoring", exc_info=True)
            return None
