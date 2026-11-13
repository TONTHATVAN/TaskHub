from uuid import UUID

from app.domain.authorization import WorkspacePermission, WorkspacePolicy
from app.domain.exceptions import (
    AccessDeniedError,
    InactiveWorkspaceMemberError,
    UserNotFoundError,
    WorkspaceMemberExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceNotFoundError,
)
from app.domain.user import User
from app.domain.user_repository import UserRepository
from app.domain.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.domain.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository, users: UserRepository) -> None:
        self._repository = repository
        self._users = users

    async def create(self, user: User, name: str) -> Workspace:
        return await self._repository.add(name, user.id)

    async def _require(
        self, user: User, workspace_id: UUID, permission: WorkspacePermission
    ) -> Workspace:
        workspace = await self._repository.get(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError
        role = None
        manager = WorkspacePolicy(user, workspace.owner_id, None).can_manage
        if not manager:
            role = await self._repository.get_member_role(
                workspace_id,
                user.id,
                for_update=permission is not WorkspacePermission.READ,
            )
        policy = WorkspacePolicy(user, workspace.owner_id, role)
        if not policy.can_read:
            raise WorkspaceNotFoundError
        if permission is WorkspacePermission.WRITE and not policy.can_write:
            raise AccessDeniedError
        if permission is WorkspacePermission.MANAGE and not policy.can_manage:
            raise AccessDeniedError
        return workspace

    async def require_read(self, user: User, workspace_id: UUID) -> Workspace:
        return await self._require(user, workspace_id, WorkspacePermission.READ)

    async def require_write(self, user: User, workspace_id: UUID) -> Workspace:
        return await self._require(user, workspace_id, WorkspacePermission.WRITE)

    async def require_manage(self, user: User, workspace_id: UUID) -> Workspace:
        return await self._require(user, workspace_id, WorkspacePermission.MANAGE)

    async def rename(self, workspace: Workspace, name: str) -> Workspace:
        updated = await self._repository.rename(workspace.id, name)
        if updated is None:
            raise WorkspaceNotFoundError
        return updated

    async def delete(self, workspace: Workspace) -> None:
        if not await self._repository.delete(workspace.id):
            raise WorkspaceNotFoundError

    async def list_members(
        self, workspace: Workspace, *, page: int, limit: int
    ) -> tuple[list[WorkspaceMember], int]:
        return await self._repository.list_members(workspace.id, page=page, limit=limit)

    async def invite_member(
        self, workspace: Workspace, member_id: UUID, role: WorkspaceRole
    ) -> WorkspaceMember:
        member = await self._users.get_by_id(member_id)
        if member is None:
            raise UserNotFoundError
        if not member.is_active:
            raise InactiveWorkspaceMemberError
        if not await self._repository.add_member(workspace.id, member_id, role):
            raise WorkspaceMemberExistsError
        return WorkspaceMember(member_id, role)

    async def remove_member(self, workspace: Workspace, member_id: UUID) -> None:
        if member_id == workspace.owner_id:
            raise AccessDeniedError
        if not await self._repository.remove_member(workspace.id, member_id):
            if await self._repository.get(workspace.id) is None:
                raise WorkspaceNotFoundError
            raise WorkspaceMemberNotFoundError
