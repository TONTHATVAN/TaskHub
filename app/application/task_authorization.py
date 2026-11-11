from uuid import UUID

from app.domain.authorization import ProjectAccess, ProjectAccessRepository
from app.domain.exceptions import (
    AccessDeniedError,
    ProjectArchivedError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from app.domain.project import ProjectStatus
from app.domain.task import Task
from app.domain.task_repository import TaskRepository
from app.domain.user import User, UserRole
from app.domain.workspace import WorkspaceRole


class TaskAuthorizationService:
    def __init__(self, access: ProjectAccessRepository, tasks: TaskRepository) -> None:
        self._access = access
        self._tasks = tasks

    async def require_project(
        self,
        user: User,
        project_id: UUID,
        *,
        write: bool,
        allow_archived: bool = False,
    ) -> ProjectAccess:
        access = await self._access.get_project_access(
            project_id, user.id, for_update=write
        )
        if access is None:
            raise ProjectNotFoundError
        if user.role != UserRole.ADMIN and access.owner_id != user.id:
            if access.member_role is None:
                raise AccessDeniedError
            if write and access.member_role not in (
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
            ):
                raise AccessDeniedError
        if write and not allow_archived and access.status is ProjectStatus.ARCHIVED:
            raise ProjectArchivedError
        return access

    async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError
        await self.require_project(user, task.project_id, write=write)
        return task
