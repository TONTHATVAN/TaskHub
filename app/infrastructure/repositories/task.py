from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import (
    InvalidTaskAssigneeError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from app.domain.task import Task, TaskPriority, TaskStatus
from app.domain.task_repository import TaskChanges
from app.infrastructure.models import (
    ProjectModel,
    TaskModel,
    UserModel,
    WorkspaceMemberModel,
)
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
            assignee_id=model.assignee_id,
            due_date=model.due_date,
            created_by=model.created_by,
        )

    async def add(self, task: Task) -> None:
        model = TaskModel(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at,
            assignee_id=task.assignee_id,
            due_date=task.due_date,
            created_by=task.created_by,
        )
        try:
            async with self._session.begin_nested():
                await self._repository.add(model)
        except IntegrityError as exc:
            project_exists = await self._session.scalar(
                select(ProjectModel.id).where(ProjectModel.id == task.project_id)
            )
            if project_exists is None:
                raise ProjectNotFoundError from exc
            raise

    async def get(self, task_id: UUID) -> Task | None:
        model = await self._repository.get(task_id)
        return self._to_domain(model) if model else None

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: UUID | None = None,
    ) -> list[Task]:
        statement = select(TaskModel).where(TaskModel.project_id == project_id)
        if status is not None:
            statement = statement.where(TaskModel.status == status)
        if priority is not None:
            statement = statement.where(TaskModel.priority == priority)
        if assignee_id is not None:
            statement = statement.where(TaskModel.assignee_id == assignee_id)
        result = await self._session.scalars(
            statement.order_by(TaskModel.created_at, TaskModel.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [self._to_domain(model) for model in result]

    async def require_assignable(self, project_id: UUID, assignee_id: UUID) -> None:
        member_id = await self._session.scalar(
            select(WorkspaceMemberModel.user_id)
            .join(
                ProjectModel,
                ProjectModel.workspace_id == WorkspaceMemberModel.workspace_id,
            )
            .join(UserModel, UserModel.id == WorkspaceMemberModel.user_id)
            .where(
                ProjectModel.id == project_id,
                WorkspaceMemberModel.user_id == assignee_id,
                UserModel.is_active.is_(True),
            )
            .with_for_update(read=True, of=(WorkspaceMemberModel, UserModel))
        )
        if member_id is None:
            raise InvalidTaskAssigneeError

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
