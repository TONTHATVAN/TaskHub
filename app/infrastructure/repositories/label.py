from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import (
    LabelAlreadyExistsError,
    LabelNotFoundError,
    TaskNotFoundError,
)
from app.domain.label import Label
from app.domain.label_repository import LabelChanges
from app.infrastructure.models import LabelModel, TaskLabelModel, TaskModel


class SqlLabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: LabelModel) -> Label:
        return Label(model.id, model.project_id, model.name, model.color)

    async def add(self, project_id: UUID, name: str, color: str) -> Label:
        model = await self._session.scalar(
            insert(LabelModel)
            .values(id=uuid4(), project_id=project_id, name=name, color=color)
            .on_conflict_do_nothing(
                index_elements=[LabelModel.project_id, LabelModel.name]
            )
            .returning(LabelModel)
        )
        if model is None:
            raise LabelAlreadyExistsError
        return self._to_domain(model)

    async def get(self, project_id: UUID, label_id: UUID) -> Label | None:
        model = await self._session.scalar(
            select(LabelModel).where(
                LabelModel.project_id == project_id, LabelModel.id == label_id
            )
        )
        return self._to_domain(model) if model is not None else None

    async def list_by_project(
        self, project_id: UUID, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[Label], int]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(LabelModel)
            .where(LabelModel.project_id == project_id)
        )
        models = await self._session.scalars(
            select(LabelModel)
            .where(LabelModel.project_id == project_id)
            .order_by(LabelModel.name, LabelModel.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [self._to_domain(model) for model in models], total or 0

    async def save(
        self, project_id: UUID, label_id: UUID, changes: LabelChanges
    ) -> Label | None:
        try:
            async with self._session.begin_nested():
                model = await self._session.scalar(
                    update(LabelModel)
                    .where(
                        LabelModel.project_id == project_id,
                        LabelModel.id == label_id,
                    )
                    .values(**changes)
                    .returning(LabelModel)
                    .execution_options(populate_existing=True)
                )
        except IntegrityError as exc:
            if "name" in changes:
                existing = await self._session.scalar(
                    select(LabelModel.id).where(
                        LabelModel.project_id == project_id,
                        LabelModel.name == changes["name"],
                    )
                )
                if existing is not None:
                    raise LabelAlreadyExistsError from exc
            raise
        return self._to_domain(model) if model is not None else None

    async def delete(self, project_id: UUID, label_id: UUID) -> bool:
        deleted = await self._session.scalar(
            delete(LabelModel)
            .where(LabelModel.project_id == project_id, LabelModel.id == label_id)
            .returning(LabelModel.id)
        )
        return deleted is not None

    async def attach(self, task_id: UUID, project_id: UUID, label_id: UUID) -> bool:
        selected = (
            select(TaskModel.id, LabelModel.id)
            .join(LabelModel, LabelModel.project_id == TaskModel.project_id)
            .where(
                TaskModel.id == task_id,
                TaskModel.project_id == project_id,
                LabelModel.id == label_id,
                LabelModel.project_id == project_id,
            )
        )
        try:
            async with self._session.begin_nested():
                attached = await self._session.scalar(
                    insert(TaskLabelModel)
                    .from_select(["task_id", "label_id"], selected)
                    .on_conflict_do_nothing()
                    .returning(TaskLabelModel.label_id)
                )
        except IntegrityError as exc:
            task_exists = await self._session.scalar(
                select(TaskModel.id).where(TaskModel.id == task_id)
            )
            if task_exists is None:
                raise TaskNotFoundError from exc
            raise LabelNotFoundError from exc
        if attached is not None:
            return True
        if (
            await self._session.scalar(
                select(TaskModel.id).where(TaskModel.id == task_id)
            )
            is None
        ):
            raise TaskNotFoundError
        return await self.get(project_id, label_id) is not None

    async def detach(self, task_id: UUID, project_id: UUID, label_id: UUID) -> bool:
        deleted = await self._session.scalar(
            delete(TaskLabelModel)
            .where(
                TaskLabelModel.task_id == task_id,
                TaskLabelModel.label_id == label_id,
                select(LabelModel.id)
                .where(
                    LabelModel.id == label_id,
                    LabelModel.project_id == project_id,
                )
                .exists(),
            )
            .returning(TaskLabelModel.label_id)
        )
        if deleted is not None:
            return True
        if (
            await self._session.scalar(
                select(TaskModel.id).where(TaskModel.id == task_id)
            )
            is None
        ):
            raise TaskNotFoundError
        return await self.get(project_id, label_id) is not None

    async def list_for_task(self, task_id: UUID) -> list[Label]:
        models = await self._session.scalars(
            select(LabelModel)
            .join(TaskLabelModel, TaskLabelModel.label_id == LabelModel.id)
            .where(TaskLabelModel.task_id == task_id)
            .order_by(LabelModel.name, LabelModel.id)
        )
        return [self._to_domain(model) for model in models]
