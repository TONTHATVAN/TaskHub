from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.project import Project
from app.domain.user import User, UserRole
from app.domain.workspace import WorkspaceRole

WRITABLE_WORKSPACE_ROLES = frozenset((WorkspaceRole.OWNER, WorkspaceRole.EDITOR))


class WorkspacePermission(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    MANAGE = "MANAGE"


@dataclass(frozen=True, slots=True)
class WorkspacePolicy:
    user: User
    owner_id: UUID
    member_role: WorkspaceRole | None

    @property
    def can_manage(self) -> bool:
        return self.user.role is UserRole.ADMIN or self.user.id == self.owner_id

    @property
    def can_read(self) -> bool:
        return self.can_manage or self.member_role is not None

    @property
    def can_write(self) -> bool:
        return self.can_manage or self.member_role in WRITABLE_WORKSPACE_ROLES


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    owner_id: UUID
    member_role: WorkspaceRole | None
    project: Project


class ProjectAccessRepository(Protocol):
    async def get_project_access(
        self, project_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> ProjectAccess | None: ...
