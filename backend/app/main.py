from fastapi import FastAPI

from app.api.v1.api import api_router
from app.core.exceptions import register_exception_handlers


def create_application() -> FastAPI:
    app = FastAPI(title="Mianshibao API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_application()
