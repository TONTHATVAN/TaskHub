from uuid import UUID

from app.domain.authorization import (
    ProjectAccess,
    ProjectAccessRepository,
    WorkspacePolicy,
)
from app.domain.exceptions import (
    AccessDeniedError,
    ProjectArchivedError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from app.domain.project import ProjectStatus
from app.domain.task import Task
from app.domain.task_repository import TaskRepository
from app.domain.user import User


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
        policy = WorkspacePolicy(user, access.owner_id, access.member_role)
        if not policy.can_read:
            raise ProjectNotFoundError
        if write and not policy.can_write:
            raise AccessDeniedError
        if (
            write
            and not allow_archived
            and access.project.status is ProjectStatus.ARCHIVED
        ):
            raise ProjectArchivedError
        return access

    async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
        task = await self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError
        try:
            await self.require_project(user, task.project_id, write=write)
        except ProjectNotFoundError as exc:
            raise TaskNotFoundError from exc
        return task
