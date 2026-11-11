from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.task import Task
from app.domain.task_repository import TaskChanges


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    async def add(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def list_by_project(
        self, project_id: UUID, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> list[Task]:
        tasks = sorted(
            (task for task in self._tasks.values() if task.project_id == project_id),
            key=lambda task: (task.created_at, task.id),
        )
        return tasks[(page - 1) * limit : page * limit]

    async def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    async def save(self, task: Task, changes: TaskChanges) -> Task:
        self._tasks[task.id] = task
        return task

    async def delete(self, task_id: UUID) -> bool:
        return self._tasks.pop(task_id, None) is not None
