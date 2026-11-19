from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.error_handling import app_error_response
from app.api.router import api_router
from app.core.exceptions import AppException
from app.infrastructure.database import engine
from app.infrastructure.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await close_redis()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TaskHub API", version="0.3.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.exception_handler(AppException)
    async def app_exception_handler(
        _request: Request, exc: AppException
    ) -> JSONResponse:
        return app_error_response(exc)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
