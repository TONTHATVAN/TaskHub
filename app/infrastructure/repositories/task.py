from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import TaskNotFoundError
from app.domain.task import Task
from app.domain.task_repository import TaskChanges
from app.infrastructure.models import ProjectModel, TaskModel
from app.infrastructure.repositories.base import BaseRepository


class SqlTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = BaseRepository(session, TaskModel)
        self._session = session

    @staticmethod
    def _to_domain(model: TaskModel) -> Task:
        return Task(
            id=model.id,
            project_id=model.project_id,
            title=model.title,
            description=model.description,
            status=model.status,
            priority=model.priority,
            created_at=model.created_at,
        )

    async def project_exists(self, project_id: UUID) -> bool:
        return await self._session.get(ProjectModel, project_id) is not None

    async def add(self, task: Task) -> None:
        model = TaskModel(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at,
        )
        await self._repository.add(model)

    async def get(self, task_id: UUID) -> Task | None:
        model = await self._repository.get(task_id)
        return self._to_domain(model) if model else None

    async def list_by_project(
        self, project_id: UUID, *, page: int = 1, limit: int = 20
    ) -> list[Task]:
        result = await self._session.scalars(
            select(TaskModel)
            .where(TaskModel.project_id == project_id)
            .order_by(TaskModel.created_at, TaskModel.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [self._to_domain(model) for model in result]

    async def save(self, task: Task, changes: TaskChanges) -> Task:
        result = await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task.id)
            .values(**changes)
            .returning(TaskModel)
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise TaskNotFoundError
        return self._to_domain(model)

    async def delete(self, task_id: UUID) -> bool:
        result = await self._session.execute(
            delete(TaskModel).where(TaskModel.id == task_id).returning(TaskModel.id)
        )
        return result.scalar_one_or_none() is not None
