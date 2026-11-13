from typing import Protocol
from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.comment import Comment


class CommentRepository(Protocol):
    async def add(self, task_id: UUID, author_id: UUID, content: str) -> Comment: ...
    async def get(self, task_id: UUID, comment_id: UUID) -> Comment | None: ...
    async def list_by_task(
        self, task_id: UUID, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[Comment], int]: ...
    async def delete(self, task_id: UUID, comment_id: UUID) -> bool: ...
