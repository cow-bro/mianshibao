import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import (
    create_token_pair,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.providers.sms import SmsProvider


class AuthService:
    _PHONE_PATTERN = re.compile(r"^(?:\+?86)?1[3-9]\d{9}$")
    _sms_provider = SmsProvider()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        normalized = phone.strip().replace(" ", "")
        if normalized.startswith("+86"):
            normalized = normalized[3:]
        return normalized

    @classmethod
    def _validate_phone(cls, phone: str) -> str:
        normalized = cls._normalize_phone(phone)
        if not cls._PHONE_PATTERN.match(normalized):
            raise AppException(message="invalid phone number", code=1006)
        return normalized

    @staticmethod
    async def _generate_unique_username(db: AsyncSession, phone: str) -> str:
        base = f"u_{phone[-4:]}"
        candidate = base
        seq = 1
        while True:
            result = await db.execute(select(User.id).where(User.username == candidate))
            if result.scalar_one_or_none() is None:
                return candidate
            seq += 1
            candidate = f"{base}_{seq}"

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

    @classmethod
    async def send_sms_code(cls, phone: str, purpose: str) -> dict:
        normalized = cls._validate_phone(phone)
        result = cls._sms_provider.send_verification_code(normalized, purpose)
        return {"request_id": result.request_id, "status": result.status}

    @classmethod
    async def register_with_phone(
        cls,
        db: AsyncSession,
        phone: str,
        password: str,
        sms_code: str | None = None,
    ) -> dict:
        normalized = cls._validate_phone(phone)
        if len(password) < 6:
            raise AppException(message="password must be at least 6 characters", code=1007)

        # Placeholder for future SMS verification.
        _ = sms_code

        existing_phone = await db.execute(select(User).where(User.phone == normalized))
        if existing_phone.scalar_one_or_none() is not None:
            raise AppException(message="phone already registered", code=1008)

        username = await cls._generate_unique_username(db, normalized)
        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            phone=normalized,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        tokens = create_token_pair(str(user.id))
        return {
            "user_id": user.id,
            "phone": normalized,
            "username": user.username,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
        }
