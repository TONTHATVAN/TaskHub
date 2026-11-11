from uuid import UUID

from app.domain.authorization import ProjectAccess, ProjectAccessRepository
from app.domain.exceptions import (
    AccessDeniedError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from app.domain.task import Task
from app.domain.task_repository import TaskRepository
from app.domain.user import User, UserRole
from app.domain.workspace import WorkspaceRole


class TaskAuthorizationService:
    def __init__(self, access: ProjectAccessRepository, tasks: TaskRepository) -> None:
        self._access = access
        self._tasks = tasks

    async def require_project(
        self, user: User, project_id: UUID, *, write: bool
    ) -> ProjectAccess:
        access = await self._access.get_project_access(project_id, user.id)
        if access is None:
            raise ProjectNotFoundError
        if user.role == UserRole.ADMIN or access.owner_id == user.id:
            return access
        if access.member_role is None:
            raise AccessDeniedError
        if write and access.member_role not in (
            WorkspaceRole.OWNER,
            WorkspaceRole.EDITOR,
        ):
            raise AccessDeniedError
        return access

    async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError
        await self.require_project(user, task.project_id, write=write)
        return task
