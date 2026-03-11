"""Embedding provider using DashScope text-embedding-v2."""

from __future__ import annotations

from dashscope import TextEmbedding

from app.core.config import get_settings


class EmbeddingProvider:
    """Wraps DashScope text-embedding-v2 to produce 1536-dim vectors."""

    MODEL = "text-embedding-v2"
    DIMENSIONS = 1536
    BATCH_SIZE = 25  # DashScope max per call

    def __init__(self) -> None:
        self.settings = get_settings()

    def embed(self, text: str) -> list[float]:
        if not self.settings.dashscope_api_key:
            return [0.0] * self.DIMENSIONS

        resp = TextEmbedding.call(
            model=self.MODEL,
            input=text,
            api_key=self.settings.dashscope_api_key,
        )
        try:
            return resp.output["embeddings"][0]["embedding"]
        except Exception as exc:
            raise RuntimeError(f"embedding call failed: {resp}") from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.dashscope_api_key:
            return [[0.0] * self.DIMENSIONS for _ in texts]

        results: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            resp = TextEmbedding.call(
                model=self.MODEL,
                input=batch,
                api_key=self.settings.dashscope_api_key,
            )
            try:
                for item in resp.output["embeddings"]:
                    results.append(item["embedding"])
            except Exception as exc:
                raise RuntimeError(f"batch embedding call failed: {resp}") from exc
        return results
