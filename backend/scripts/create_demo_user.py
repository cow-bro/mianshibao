from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User, UserRole


async def main() -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "demo"))
        user = result.scalar_one_or_none()
        if user is None:
            db.add(
                User(
                    username="demo",
                    hashed_password="demo123",
                    role=UserRole.USER,
                    is_active=True,
                )
            )
            await db.commit()
            print("demo created")
        else:
            print("demo already exists")


if __name__ == "__main__":
    asyncio.run(main())
