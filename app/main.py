from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.exceptions import AppException
from app.infrastructure.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TaskHub API", version="0.3.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.exception_handler(AppException)
    async def app_exception_handler(
        _request: Request, exc: AppException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers=exc.headers,
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
