from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole


async def main() -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "demo"))
        user = result.scalar_one_or_none()
        password_hash = get_password_hash("demo123")
        if user is None:
            db.add(
                User(
                    username="demo",
                    hashed_password=password_hash,
                    role=UserRole.USER,
                    is_active=True,
                )
            )
            await db.commit()
            print("demo created")
        else:
            user.hashed_password = password_hash
            user.is_active = True
            if user.role is None:
                user.role = UserRole.USER
            await db.commit()
            print("demo already exists")


if __name__ == "__main__":
    asyncio.run(main())
