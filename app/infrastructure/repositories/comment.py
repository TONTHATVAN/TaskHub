from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.comment import Comment
from app.domain.exceptions import TaskNotFoundError, UserNotFoundError
from app.infrastructure.models import CommentModel, TaskModel


class SqlCommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: CommentModel) -> Comment:
        return Comment(
            model.id, model.task_id, model.author_id, model.content, model.created_at
        )

    async def add(self, task_id: UUID, author_id: UUID, content: str) -> Comment:
        try:
            async with self._session.begin_nested():
                model = await self._session.scalar(
                    insert(CommentModel)
                    .values(
                        id=uuid4(),
                        task_id=task_id,
                        author_id=author_id,
                        content=content,
                    )
                    .returning(CommentModel)
                )
        except IntegrityError as exc:
            task_exists = await self._session.scalar(
                select(TaskModel.id).where(TaskModel.id == task_id)
            )
            if task_exists is None:
                raise TaskNotFoundError from exc
            raise UserNotFoundError from exc
        assert model is not None
        return self._to_domain(model)

    async def get(self, task_id: UUID, comment_id: UUID) -> Comment | None:
        model = await self._session.scalar(
            select(CommentModel).where(
                CommentModel.task_id == task_id, CommentModel.id == comment_id
            )
        )
        return self._to_domain(model) if model is not None else None

    async def list_by_task(
        self, task_id: UUID, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[Comment], int]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(CommentModel)
            .where(CommentModel.task_id == task_id)
        )
        models = await self._session.scalars(
            select(CommentModel)
            .where(CommentModel.task_id == task_id)
            .order_by(CommentModel.created_at, CommentModel.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [self._to_domain(model) for model in models], total or 0

    async def delete(self, task_id: UUID, comment_id: UUID) -> bool:
        deleted = await self._session.scalar(
            delete(CommentModel)
            .where(CommentModel.task_id == task_id, CommentModel.id == comment_id)
            .returning(CommentModel.id)
        )
        return deleted is not None
