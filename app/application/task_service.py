from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import TaskNotFoundError
from app.domain.task import Task, TaskPriority, TaskStatus
from app.domain.task_cache import TaskCacheService
from app.domain.task_repository import TaskChanges, TaskRepository


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        cache: TaskCacheService | None = None,
    ) -> None:
        self._repository = repository
        self._cache = cache

    async def create(
        self,
        project_id: UUID,
        title: str,
        description: str | None,
        status: TaskStatus,
        priority: TaskPriority,
        created_by: UUID,
        assignee_id: UUID | None = None,
        due_date: datetime | None = None,
    ) -> Task:
        if assignee_id is not None:
            await self._repository.require_assignable(project_id, assignee_id)
        task = Task(
            id=uuid4(),
            project_id=project_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            created_at=datetime.now(UTC),
            assignee_id=assignee_id,
            due_date=due_date,
            created_by=created_by,
        )
        await self._repository.add(task)
        await self._repository.commit()
        if self._cache is not None:
            await self._cache.invalidate_project(project_id)
        return task

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Task]:
        if self._cache is not None:
            cached = await self._cache.get_tasks(
                project_id,
                page=page,
                limit=limit,
                status=status,
                priority=priority,
                assignee_id=assignee_id,
            )
            if cached is not None:
                return cached
        tasks = await self._repository.list_by_project(
            project_id,
            page=page,
            limit=limit,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
        )
        if self._cache is not None:
            await self._cache.set_tasks(
                project_id,
                page=page,
                limit=limit,
                status=status,
                priority=priority,
                assignee_id=assignee_id,
                tasks=tasks,
            )
        return tasks

    async def get(self, task_id: UUID) -> Task:
        task = await self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError
        return task

    async def update(self, task: Task, changes: TaskChanges) -> Task:
        if "assignee_id" in changes and changes["assignee_id"] is not None:
            await self._repository.require_assignable(
                task.project_id, changes["assignee_id"]
            )
        updated_task = replace(task, **changes)
        if changes:
            saved_task = await self._repository.save(updated_task, changes)
            await self._repository.commit()
            if self._cache is not None:
                await self._cache.invalidate_project(task.project_id)
            return saved_task
        return updated_task

    async def delete(self, task: Task) -> None:
        if not await self._repository.delete(task.id):
            raise TaskNotFoundError
        await self._repository.commit()
        if self._cache is not None:
            await self._cache.invalidate_project(task.project_id)
