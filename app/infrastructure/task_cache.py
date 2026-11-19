import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.task import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


def serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "project_id": str(task.project_id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority.value,
        "created_at": task.created_at.isoformat(),
        "assignee_id": str(task.assignee_id) if task.assignee_id is not None else None,
        "due_date": task.due_date.isoformat() if task.due_date is not None else None,
        "created_by": str(task.created_by) if task.created_by is not None else None,
    }


def deserialize_task(data: dict[str, Any]) -> Task:
    return Task(
        id=UUID(data["id"]),
        project_id=UUID(data["project_id"]),
        title=data["title"],
        description=data.get("description"),
        status=TaskStatus(data["status"]),
        priority=TaskPriority(data["priority"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        assignee_id=UUID(data["assignee_id"]) if data.get("assignee_id") else None,
        due_date=datetime.fromisoformat(data["due_date"])
        if data.get("due_date")
        else None,
        created_by=UUID(data["created_by"]) if data.get("created_by") else None,
    )


def build_task_cache_key(
    project_id: UUID,
    *,
    page: int,
    limit: int,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee_id: UUID | None = None,
) -> str:
    status_part = status.value if status is not None else "all"
    priority_part = priority.value if priority is not None else "all"
    assignee_part = str(assignee_id) if assignee_id is not None else "all"
    return (
        f"taskhub:tasks:{project_id}:p={page}:l={limit}:"
        f"s={status_part}:pr={priority_part}:a={assignee_part}"
    )


class RedisTaskCacheService:
    def __init__(self, redis: Redis, ttl_seconds: int = 300) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def get_tasks(
        self,
        project_id: UUID,
        *,
        page: int,
        limit: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Task] | None:
        key = build_task_cache_key(
            project_id,
            page=page,
            limit=limit,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
        )
        try:
            cached = await self._redis.get(key)
            if cached is None:
                return None
            data = json.loads(cached)
            return [deserialize_task(item) for item in data]
        except (RedisError, json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Redis cache get error for key %s: %s", key, exc)
            return None

    async def set_tasks(
        self,
        project_id: UUID,
        *,
        page: int,
        limit: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        tasks: list[Task],
    ) -> None:
        key = build_task_cache_key(
            project_id,
            page=page,
            limit=limit,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
        )
        try:
            serialized = json.dumps([serialize_task(task) for task in tasks])
            await self._redis.set(key, serialized, ex=self._ttl)
        except RedisError as exc:
            logger.warning("Redis cache set error for key %s: %s", key, exc)

    async def invalidate_project(self, project_id: UUID) -> None:
        pattern = f"taskhub:tasks:{project_id}:*"
        try:
            keys: list[str] = []
            async for key in self._redis.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
        except RedisError as exc:
            logger.warning(
                "Redis cache invalidate error for project %s: %s", project_id, exc
            )

    async def invalidate_all(self) -> None:
        pattern = "taskhub:tasks:*"
        try:
            keys: list[str] = []
            async for key in self._redis.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
        except RedisError as exc:
            logger.warning("Redis cache invalidate all error: %s", exc)


class InMemoryTaskCacheService:
    def __init__(self) -> None:
        self._cache: dict[str, list[Task]] = {}
        self.get_calls = 0
        self.set_calls = 0
        self.invalidate_calls = 0

    async def get_tasks(
        self,
        project_id: UUID,
        *,
        page: int,
        limit: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Task] | None:
        self.get_calls += 1
        key = build_task_cache_key(
            project_id,
            page=page,
            limit=limit,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
        )
        return self._cache.get(key)

    async def set_tasks(
        self,
        project_id: UUID,
        *,
        page: int,
        limit: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
        tasks: list[Task],
    ) -> None:
        self.set_calls += 1
        key = build_task_cache_key(
            project_id,
            page=page,
            limit=limit,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
        )
        self._cache[key] = list(tasks)

    async def invalidate_project(self, project_id: UUID) -> None:
        self.invalidate_calls += 1
        prefix = f"taskhub:tasks:{project_id}:"
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]

    async def invalidate_all(self) -> None:
        self.invalidate_calls += 1
        self._cache.clear()
