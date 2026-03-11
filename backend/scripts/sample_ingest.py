"""Sample scaffold for ingesting CSV/JSON into knowledge_point.

This file is intentionally pseudo-code oriented. Fill in the embedding provider
and concrete data source fields before production use.
"""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.models.knowledge_point import DifficultyLevel, KnowledgePoint, KnowledgePointType


class EmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        # TODO: replace with your real embedding API call (OpenAI/Qwen/etc.)
        return [0.0] * 1536


async def load_rows(input_path: Path) -> list[dict]:
    if input_path.suffix.lower() == ".csv":
        with input_path.open("r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    if input_path.suffix.lower() == ".json":
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data

    raise ValueError("Only CSV/JSON list files are supported")


def map_row_to_entity(row: dict, embedding: list[float]) -> KnowledgePoint:
    return KnowledgePoint(
        subject=row.get("subject", "Computer Science"),
        category=row.get("category", "General"),
        type=KnowledgePointType(row.get("type", "KNOWLEDGE")),
        difficulty=DifficultyLevel(row.get("difficulty", "MEDIUM")),
        title=row.get("title", "Untitled"),
        content=row.get("content", ""),
        answer=row.get("answer"),
        source_company=row.get("source_company"),
        tags=row.get("tags", []),
        embedding=embedding,
    )


async def ingest_file(input_path: Path, batch_size: int = 100) -> None:
    embedder = EmbeddingClient()
    rows = await load_rows(input_path)

    async with SessionLocal() as db:
        buffer: list[KnowledgePoint] = []
        for row in rows:
            text_for_embedding = f"{row.get('title', '')}\n{row.get('content', '')}"
            vector = await embedder.embed(text_for_embedding)
            buffer.append(map_row_to_entity(row, vector))

            if len(buffer) >= batch_size:
                db.add_all(buffer)
                await db.commit()
                buffer.clear()

        if buffer:
            db.add_all(buffer)
            await db.commit()


if __name__ == "__main__":
    # Example: python -m scripts.sample_ingest ./sample_knowledge.json
    target = Path("./sample_knowledge.json")
    asyncio.run(ingest_file(target))
