"""Ingest knowledge cards from JSON / Markdown files into the database."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.services.knowledge_service import KnowledgeService


def parse_markdown_cards(text: str) -> list[dict]:
    """Parse markdown-formatted knowledge cards.

    Expected format per card (separated by ``## ``):

        ## Title
        - subject: xxx
        - category: xxx
        - difficulty: EASY|MEDIUM|HARD
        - tags: tag1, tag2

        Content goes here ...

        ### Answer
        Answer goes here ...
    """
    cards: list[dict] = []
    sections = re.split(r"(?:^|\n)## ", text)
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split("\n")
        title = lines[0].strip()

        metadata: dict[str, str] = {}
        content_start = 1
        for i, line in enumerate(lines[1:], 1):
            stripped = line.strip()
            if stripped.startswith("- "):
                kv = stripped[2:].split(":", 1)
                if len(kv) == 2:
                    metadata[kv[0].strip().lower()] = kv[1].strip()
                    content_start = i + 1
            elif stripped == "" and i == content_start:
                content_start = i + 1
            else:
                break

        remaining = "\n".join(lines[content_start:])
        answer: str | None = None
        for sep in ("### Answer", "### 答案"):
            if sep in remaining:
                parts = remaining.split(sep, 1)
                remaining = parts[0].strip()
                answer = parts[1].strip() if len(parts) > 1 else None
                break
        content = remaining.strip()
        if not content:
            continue

        tags_str = metadata.get("tags", "")
        tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

        cards.append(
            {
                "subject": metadata.get("subject", "Computer Science"),
                "category": metadata.get("category", "General"),
                "type": metadata.get("type", "KNOWLEDGE"),
                "difficulty": metadata.get("difficulty", "MEDIUM"),
                "title": title,
                "content": content,
                "answer": answer,
                "source_company": metadata.get("source_company"),
                "tags": tags,
            }
        )
    return cards


async def ingest_from_file(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8") as f:
        if path.suffix.lower() == ".json":
            cards = json.load(f)
        elif path.suffix.lower() in (".md", ".markdown"):
            cards = parse_markdown_cards(f.read())
        else:
            print(f"Unsupported file format: {path.suffix}")
            sys.exit(1)

    if not isinstance(cards, list):
        print("Input must be a JSON array of knowledge cards")
        sys.exit(1)

    service = KnowledgeService()
    async with SessionLocal() as db:
        ids = await service.ingest_cards(db, cards)
        print(f"Successfully ingested {len(ids)} knowledge cards. IDs: {ids}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ingest_knowledge <file_path>")
        print("Supported formats: .json, .md")
        sys.exit(1)

    asyncio.run(ingest_from_file(sys.argv[1]))


if __name__ == "__main__":
    main()
