from uuid import UUID

from app.domain.task import Task


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    async def add(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def list_by_project(self, project_id: UUID) -> list[Task]:
        return [task for task in self._tasks.values() if task.project_id == project_id]

    async def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    async def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def delete(self, task_id: UUID) -> bool:
        return self._tasks.pop(task_id, None) is not None
