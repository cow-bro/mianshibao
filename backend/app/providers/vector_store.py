from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ping_vector_extension(db: AsyncSession) -> bool:
    # Lightweight check used by health/readiness logic.
    result = await db.execute(text("SELECT 1"))
    return result.scalar_one() == 1
