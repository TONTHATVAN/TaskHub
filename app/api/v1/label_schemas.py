from typing import Annotated, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import (
    LABEL_COLOR_LENGTH,
    LABEL_NAME_MAX_LENGTH,
    LABEL_NAME_MIN_LENGTH,
)
from app.core.messages import NULL_REQUIRED_FIELD_MESSAGE
from app.domain.label_repository import LabelChanges

LabelName = Annotated[
    str, Field(min_length=LABEL_NAME_MIN_LENGTH, max_length=LABEL_NAME_MAX_LENGTH)
]
LabelColor = Annotated[
    str,
    Field(
        min_length=LABEL_COLOR_LENGTH,
        max_length=LABEL_COLOR_LENGTH,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    ),
]


class LabelPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class LabelCreate(LabelPayload):
    name: LabelName
    color: LabelColor


class LabelUpdate(LabelPayload):
    name: LabelName | None = None
    color: LabelColor | None = None

    @field_validator("name", "color", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError(NULL_REQUIRED_FIELD_MESSAGE)
        return value

    def to_changes(self) -> LabelChanges:
        return cast(LabelChanges, self.model_dump(exclude_unset=True))


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    name: str
    color: str
