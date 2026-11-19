from typing import Any

import pytest
from fastapi import FastAPI

from app.api.dependencies import get_task_cache_service
from app.infrastructure.task_cache import InMemoryTaskCacheService


@pytest.fixture(autouse=True)
def default_in_memory_task_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> InMemoryTaskCacheService:
    cache = InMemoryTaskCacheService()
    monkeypatch.setattr("app.api.dependencies.get_task_cache_service", lambda: cache)

    original_init = FastAPI.__init__

    def patched_init(self: FastAPI, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.dependency_overrides[get_task_cache_service] = lambda: cache

    monkeypatch.setattr(FastAPI, "__init__", patched_init)
    return cache
