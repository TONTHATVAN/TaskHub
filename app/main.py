from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.task_repository = InMemoryTaskRepository()
    yield
    del app.state.task_repository


def create_app() -> FastAPI:
    app = FastAPI(title="TaskHub API", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
