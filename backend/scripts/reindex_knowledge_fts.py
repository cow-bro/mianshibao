"""Re-index all knowledge_point search_vector with jieba Chinese segmentation.

Run after upgrading to jieba-based FTS to refresh existing records:

    docker compose exec backend python -m scripts.reindex_knowledge_fts
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import SessionLocal
from app.utils.text_splitter import segment_chinese


async def reindex() -> None:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                text("SELECT id, title, content, tags FROM knowledge_point ORDER BY id")
            )
        ).mappings().all()

        if not rows:
            print("No knowledge points found, nothing to re-index.")
            return

        count = 0
        for row in rows:
            raw = f"{row['title']} {row['content']} {' '.join(row['tags'] or [])}"
            segmented = segment_chinese(raw)
            await db.execute(
                text(
                    "UPDATE knowledge_point "
                    "SET search_vector = to_tsvector('simple', :seg_text) "
                    "WHERE id = :kp_id"
                ),
                {"seg_text": segmented, "kp_id": row["id"]},
            )
            count += 1
            if count % 100 == 0:
                await db.commit()
                print(f"  Progress: {count}/{len(rows)}")

        await db.commit()
        print(f"Re-indexed {count} knowledge points with jieba segmentation.")


def main() -> None:
    asyncio.run(reindex())


if __name__ == "__main__":
    main()
