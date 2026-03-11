from typing import Any

from app.schemas.common import ApiResponse


def success_response(data: Any = None, message: str = "success", code: int = 0) -> dict:
    return ApiResponse(code=code, message=message, data=data).model_dump()


def error_response(message: str = "error", code: int = 1, data: Any = None) -> dict:
    return ApiResponse(code=code, message=message, data=data).model_dump()
