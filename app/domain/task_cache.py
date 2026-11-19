from typing import Protocol
from uuid import UUID

from app.domain.task import Task, TaskPriority, TaskStatus


class TaskCacheService(Protocol):
    async def get_tasks(
        self,
        project_id: UUID,
        *,
        page: int,
        limit: int,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Task] | None: ...

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
    ) -> None: ...

    async def invalidate_project(self, project_id: UUID) -> None: ...

    async def invalidate_all(self) -> None: ...
