from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.response import success_response
from app.schemas.auth import LoginRequest, RefreshTokenRequest
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
