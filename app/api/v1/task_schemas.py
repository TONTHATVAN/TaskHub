from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.core.constants import TASK_TITLE_MAX_LENGTH, TASK_TITLE_MIN_LENGTH
from app.core.messages import NULL_REQUIRED_FIELD_MESSAGE, PAST_DUE_DATE_MESSAGE
from app.domain.task import TaskPriority, TaskStatus
from app.domain.task_repository import TaskChanges

TaskTitle = Annotated[
    str, Field(min_length=TASK_TITLE_MIN_LENGTH, max_length=TASK_TITLE_MAX_LENGTH)
]


def validate_due_date(value: datetime) -> datetime:
    if value < datetime.now(UTC):
        raise ValueError(PAST_DUE_DATE_MESSAGE)
    return value


TaskDueDate = Annotated[AwareDatetime, AfterValidator(validate_due_date)]


class TaskPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TaskCreate(TaskPayload):
    title: TaskTitle
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: UUID | None = None
    due_date: TaskDueDate | None = None


class TaskUpdate(TaskPayload):
    title: TaskTitle | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: UUID | None = None
    due_date: TaskDueDate | None = None

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
    assignee_id: UUID | None
    due_date: datetime | None
    created_by: UUID | None
    created_at: datetime
