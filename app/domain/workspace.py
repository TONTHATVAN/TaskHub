from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    user_id: UUID
    role: WorkspaceRole
