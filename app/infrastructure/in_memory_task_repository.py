from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import InvalidTaskAssigneeError
from app.domain.task import Task, TaskPriority, TaskStatus
from app.domain.task_repository import TaskChanges


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}
        self.assignable_users: set[UUID] = set()

    async def add(self, task: Task) -> None:
        self._tasks[task.id] = task

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
        tasks = sorted(
            (
                task
                for task in self._tasks.values()
                if task.project_id == project_id
                and (status is None or task.status == status)
                and (priority is None or task.priority == priority)
                and (assignee_id is None or task.assignee_id == assignee_id)
            ),
            key=lambda task: (task.created_at, task.id),
        )
        return tasks[(page - 1) * limit : page * limit]

    async def require_assignable(self, project_id: UUID, assignee_id: UUID) -> None:
        if assignee_id not in self.assignable_users:
            raise InvalidTaskAssigneeError

    async def get(self, task_id: UUID) -> Task | None:
        return self._tasks.get(task_id)

    async def save(self, task: Task, changes: TaskChanges) -> Task:
        self._tasks[task.id] = task
        return task

    async def delete(self, task_id: UUID) -> bool:
        return self._tasks.pop(task_id, None) is not None
