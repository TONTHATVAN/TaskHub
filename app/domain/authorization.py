from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.project import ProjectStatus
from app.domain.workspace import WorkspaceRole


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    owner_id: UUID
    member_role: WorkspaceRole | None
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectAccessRepository(Protocol):
    async def get_project_access(
        self, project_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> ProjectAccess | None: ...
