from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import WORKSPACE_NAME_MAX_LENGTH, WORKSPACE_NAME_MIN_LENGTH
from app.domain.workspace import WorkspaceRole


class WorkspaceNamePayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

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


class WorkspaceMemberInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    role: Literal[WorkspaceRole.EDITOR, WorkspaceRole.VIEWER]


class WorkspaceMemberRead(BaseModel):
    user_id: UUID
    role: WorkspaceRole
