from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import create_token_pair, decode_token, verify_password
from app.models.user import User


class AuthService:
    @staticmethod
    async def login(db: AsyncSession, username: str, password: str) -> dict:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.hashed_password):
            raise AppException(message="invalid username or password", code=1003)
        if not user.is_active:
            raise AppException(message="inactive user", code=1004)

        return create_token_pair(str(user.id))

    @staticmethod
    async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AppException(message="invalid refresh token", code=1001)

        subject = payload.get("sub")
        if not subject or not str(subject).isdigit():
            raise AppException(message="invalid token subject", code=1002)

        stmt = select(User).where(User.id == int(subject))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise AppException(message="user not available", code=1005)

        return create_token_pair(str(user.id))
