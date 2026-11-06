from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import TASK_TITLE_MAX_LENGTH, TASK_TITLE_MIN_LENGTH
from app.core.messages import NULL_REQUIRED_FIELD_MESSAGE
from app.domain.task import TaskPriority, TaskStatus
from app.domain.task_repository import TaskChanges

TaskTitle = Annotated[
    str, Field(min_length=TASK_TITLE_MIN_LENGTH, max_length=TASK_TITLE_MAX_LENGTH)
]


class TaskPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TaskCreate(TaskPayload):
    title: TaskTitle
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskUpdate(TaskPayload):
    title: TaskTitle | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

    @field_validator("title", "status", "priority", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError(NULL_REQUIRED_FIELD_MESSAGE)
        return value

    def to_changes(self) -> TaskChanges:
        return cast(TaskChanges, self.model_dump(exclude_unset=True))


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime


class ErrorRead(BaseModel):
    detail: str
