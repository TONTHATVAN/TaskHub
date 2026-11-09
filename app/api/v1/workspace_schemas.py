from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import WORKSPACE_NAME_MAX_LENGTH, WORKSPACE_NAME_MIN_LENGTH


class WorkspaceNamePayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        min_length=WORKSPACE_NAME_MIN_LENGTH, max_length=WORKSPACE_NAME_MAX_LENGTH
    )


class WorkspaceCreate(WorkspaceNamePayload):
    pass


class WorkspaceUpdate(WorkspaceNamePayload):
    pass


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
