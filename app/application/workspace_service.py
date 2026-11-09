from uuid import UUID

from app.domain.exceptions import AccessDeniedError, WorkspaceNotFoundError
from app.domain.user import User, UserRole
from app.domain.workspace import Workspace
from app.domain.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    async def create(self, user: User, name: str) -> Workspace:
        return await self._repository.add(name, user.id)

    async def get(self, user: User, workspace_id: UUID) -> Workspace:
        workspace = await self._repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError
        if user.role != UserRole.ADMIN and workspace.owner_id != user.id:
            raise AccessDeniedError
        return workspace

    async def rename(self, user: User, workspace_id: UUID, name: str) -> Workspace:
        await self.get(user, workspace_id)
        updated = await self._repository.rename(workspace_id, name)
        if updated is None:
            raise WorkspaceNotFoundError
        return updated

    async def delete(self, user: User, workspace_id: UUID) -> None:
        await self.get(user, workspace_id)
        if not await self._repository.delete(workspace_id):
            raise WorkspaceNotFoundError
