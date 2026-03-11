from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import error_response


class AppException(Exception):
    def __init__(self, message: str, code: int = 1000):
        self.message = message
        self.code = code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(status_code=400, content=error_response(message=exc.message, code=exc.code))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(status_code=exc.status_code, content=error_response(message=message, code=exc.status_code))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_response(message="validation error", code=422, data=exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=error_response(message="internal server error", code=500))
