from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Comment:
    id: UUID
    task_id: UUID
    author_id: UUID
    content: str
    created_at: datetime
