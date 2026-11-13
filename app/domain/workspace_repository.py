from typing import Protocol
from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.workspace import Workspace, WorkspaceMember, WorkspaceRole


class WorkspaceRepository(Protocol):
    async def add(self, name: str, owner_id: UUID) -> Workspace: ...

    async def get(self, workspace_id: UUID) -> Workspace | None: ...

    async def rename(self, workspace_id: UUID, name: str) -> Workspace | None: ...

    async def delete(self, workspace_id: UUID) -> bool: ...

    async def get_member_role(
        self, workspace_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> WorkspaceRole | None: ...

    async def list_members(
        self,
        workspace_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
    ) -> tuple[list[WorkspaceMember], int]: ...

    async def add_member(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool: ...

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool: ...
