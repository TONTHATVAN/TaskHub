from typing import Protocol, TypedDict
from uuid import UUID

from app.domain.task import Task, TaskPriority, TaskStatus


class TaskChanges(TypedDict, total=False):
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority


class TaskRepository(Protocol):
    async def project_exists(self, project_id: UUID) -> bool: ...

    async def add(self, task: Task) -> None: ...

    async def list_by_project(
        self, project_id: UUID, *, page: int = 1, limit: int = 20
    ) -> list[Task]: ...

    async def get(self, task_id: UUID) -> Task | None: ...

    async def save(self, task: Task, changes: TaskChanges) -> Task: ...

    async def delete(self, task_id: UUID) -> bool: ...
