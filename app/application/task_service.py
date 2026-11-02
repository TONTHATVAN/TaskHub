from dataclasses import replace
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

from app.domain.task import Task, TaskPriority, TaskStatus
from app.domain.task_repository import TaskRepository


class TaskChanges(TypedDict, total=False):
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority


class ProjectNotFoundError(Exception):
    pass


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    async def create(
        self,
        project_id: UUID,
        title: str,
        description: str | None,
        status: TaskStatus,
        priority: TaskPriority,
    ) -> Task:
        if not await self._repository.project_exists(project_id):
            raise ProjectNotFoundError
        task = Task(
            id=uuid4(),
            project_id=project_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            created_at=datetime.now(UTC),
        )
        await self._repository.add(task)
        return task

    async def list_by_project(
        self, project_id: UUID, *, page: int = 1, limit: int = 20
    ) -> list[Task]:
        return await self._repository.list_by_project(project_id, page=page, limit=limit)

    async def get(self, task_id: UUID) -> Task | None:
        return await self._repository.get(task_id)

    async def update(self, task_id: UUID, changes: TaskChanges) -> Task | None:
        task = await self._repository.get(task_id)
        if task is None:
            return None

        updated_task = replace(task, **changes)
        await self._repository.save(updated_task)
        return updated_task

    async def delete(self, task_id: UUID) -> bool:
        return await self._repository.delete(task_id)
