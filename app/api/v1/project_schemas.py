from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PROJECT_NAME_MAX_LENGTH, PROJECT_NAME_MIN_LENGTH
from app.core.messages import NULL_REQUIRED_FIELD_MESSAGE
from app.domain.project import ProjectStatus
from app.domain.project_repository import ProjectChanges

ProjectName = Annotated[
    str, Field(min_length=PROJECT_NAME_MIN_LENGTH, max_length=PROJECT_NAME_MAX_LENGTH)
]


class ProjectPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ProjectCreate(ProjectPayload):
    name: ProjectName
    description: str | None = None


class ProjectUpdate(ProjectPayload):
    name: ProjectName | None = None
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def reject_null_name(cls, value: object) -> object:
        if value is None:
            raise ValueError(NULL_REQUIRED_FIELD_MESSAGE)
        return value

    def to_changes(self) -> ProjectChanges:
        return cast(ProjectChanges, self.model_dump(exclude_unset=True))


class ProjectRead(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
