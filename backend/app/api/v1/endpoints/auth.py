from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.response import success_response
from app.schemas.auth import (
    LoginRequest,
    PhoneRegisterRequest,
    RefreshTokenRequest,
    SendSmsCodeRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", summary="Login and issue JWT tokens")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    tokens = await AuthService.login(db, payload.username, payload.password)
    return success_response(data=tokens)


@router.post("/refresh", summary="Refresh JWT tokens")
async def refresh_tokens(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)) -> dict:
    tokens = await AuthService.refresh_tokens(db, payload.refresh_token)
    return success_response(data=tokens)


@router.post("/sms/send", summary="Send SMS verification code (placeholder)")
async def send_sms_code(payload: SendSmsCodeRequest) -> dict:
    result = await AuthService.send_sms_code(payload.phone, payload.purpose)
    return success_response(data=result)


@router.post("/register/phone", summary="Register account with phone number")
async def register_with_phone(payload: PhoneRegisterRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await AuthService.register_with_phone(
        db,
        phone=payload.phone,
        password=payload.password,
        sms_code=payload.sms_code,
    )
    return success_response(data=result)
