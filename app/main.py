from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.v1.task_constants import PROJECT_NOT_FOUND_MESSAGE, TASK_NOT_FOUND_MESSAGE
from app.domain.exceptions import NotFoundError, ProjectNotFoundError
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

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        message = (
            PROJECT_NOT_FOUND_MESSAGE
            if isinstance(exc, ProjectNotFoundError)
            else TASK_NOT_FOUND_MESSAGE
        )
        return JSONResponse(status_code=404, content={"detail": message})

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
