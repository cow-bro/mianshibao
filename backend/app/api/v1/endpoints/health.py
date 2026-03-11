from fastapi import APIRouter

from app.core.response import success_response

router = APIRouter()


@router.get("", summary="Health check")
def health_check() -> dict:
    return success_response(data={"status": "ok"})
