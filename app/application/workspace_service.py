from uuid import UUID

from app.domain.exceptions import (
    AccessDeniedError,
    InactiveWorkspaceMemberError,
    UserNotFoundError,
    WorkspaceMemberExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceNotFoundError,
)
from app.domain.user import User, UserRole
from app.domain.user_repository import UserRepository
from app.domain.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.domain.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository, users: UserRepository) -> None:
        self._repository = repository
        self._users = users

    async def create(self, user: User, name: str) -> Workspace:
        return await self._repository.add(name, user.id)

    async def get(self, user: User, workspace_id: UUID) -> Workspace:
        workspace = await self._repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError
        if (
            user.role != UserRole.ADMIN
            and workspace.owner_id != user.id
            and await self._repository.get_member_role(workspace_id, user.id) is None
        ):
            raise AccessDeniedError
        return workspace

    async def _require_manager(self, user: User, workspace_id: UUID) -> Workspace:
        workspace = await self._repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError
        if user.role != UserRole.ADMIN and workspace.owner_id != user.id:
            raise AccessDeniedError
        return workspace

    async def require_write(self, user: User, workspace_id: UUID) -> Workspace:
        workspace = await self._repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError
        if user.role == UserRole.ADMIN or workspace.owner_id == user.id:
            return workspace
        role = await self._repository.get_member_role(workspace_id, user.id)
        if role not in (WorkspaceRole.OWNER, WorkspaceRole.EDITOR):
            raise AccessDeniedError
        return workspace

    async def rename(self, user: User, workspace_id: UUID, name: str) -> Workspace:
        await self._require_manager(user, workspace_id)
        updated = await self._repository.rename(workspace_id, name)
        if updated is None:
            raise WorkspaceNotFoundError
        return updated

    async def delete(self, user: User, workspace_id: UUID) -> None:
        await self._require_manager(user, workspace_id)
        if not await self._repository.delete(workspace_id):
            raise WorkspaceNotFoundError

    async def list_members(
        self, user: User, workspace_id: UUID
    ) -> list[WorkspaceMember]:
        await self.get(user, workspace_id)
        return await self._repository.list_members(workspace_id)

    async def invite_member(
        self, user: User, workspace_id: UUID, member_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        await self._require_manager(user, workspace_id)
        if role is WorkspaceRole.OWNER:
            raise AccessDeniedError
        member = await self._users.get_by_id(member_id)
        if member is None:
            raise UserNotFoundError
        if not member.is_active:
            raise InactiveWorkspaceMemberError
        if not await self._repository.add_member(workspace_id, member_id, role):
            raise WorkspaceMemberExistsError
        return WorkspaceMember(member_id, role)

    async def remove_member(
        self, user: User, workspace_id: UUID, member_id: UUID
    ) -> None:
        workspace = await self._require_manager(user, workspace_id)
        if member_id == workspace.owner_id:
            raise AccessDeniedError
        if not await self._repository.remove_member(workspace_id, member_id):
            if await self._repository.get(workspace_id) is None:
                raise WorkspaceNotFoundError
            raise WorkspaceMemberNotFoundError
