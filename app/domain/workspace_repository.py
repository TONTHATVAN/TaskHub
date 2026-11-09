from typing import Protocol
from uuid import UUID

from app.domain.workspace import Workspace


class WorkspaceRepository(Protocol):
    async def add(self, name: str, owner_id: UUID) -> Workspace: ...

    async def get(self, workspace_id: UUID) -> Workspace | None: ...

    async def rename(self, workspace_id: UUID, name: str) -> Workspace | None: ...

    async def delete(self, workspace_id: UUID) -> bool: ...
