from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
