from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import COMMENT_CONTENT_MAX_LENGTH, COMMENT_CONTENT_MIN_LENGTH

CommentContent = Annotated[
    str,
    Field(min_length=COMMENT_CONTENT_MIN_LENGTH, max_length=COMMENT_CONTENT_MAX_LENGTH),
]


class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    content: CommentContent


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_id: UUID
    author_id: UUID
    content: str
    created_at: datetime
