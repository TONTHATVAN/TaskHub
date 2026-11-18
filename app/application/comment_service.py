from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.authorization import ProjectAccess, WorkspacePolicy
from app.domain.comment import Comment
from app.domain.comment_repository import CommentRepository
from app.domain.exceptions import AccessDeniedError, CommentNotFoundError
from app.domain.task import Task
from app.domain.user import User


class CommentService:
    def __init__(self, repository: CommentRepository) -> None:
        self._repository = repository

    async def create(self, task: Task, author: User, content: str) -> Comment:
        return await self._repository.add(task.id, author.id, content)

    async def list_by_task(
        self, task: Task, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[Comment], int]:
        return await self._repository.list_by_task(task.id, page=page, limit=limit)

    async def delete(
        self, task: Task, access: ProjectAccess, comment_id: UUID, user: User
    ) -> None:
        comment = await self._repository.get(task.id, comment_id)
        if comment is None:
            raise CommentNotFoundError
        if (
            comment.author_id != user.id
            and not WorkspacePolicy(
                user, access.owner_id, access.member_role
            ).can_manage
        ):
            raise AccessDeniedError
        if not await self._repository.delete(task.id, comment_id):
            raise CommentNotFoundError
