from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import WorkspaceNotFoundError
from app.domain.project import Project
from app.domain.project_repository import ProjectChanges
from app.infrastructure.models import ProjectModel, WorkspaceModel


class SqlProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            workspace_id=model.workspace_id,
            name=model.name,
            description=model.description,
            status=model.status,
            created_at=model.created_at,
        )

    async def add(
        self, workspace_id: UUID, name: str, description: str | None
    ) -> Project:
        model = ProjectModel(
            id=uuid4(), workspace_id=workspace_id, name=name, description=description
        )
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            workspace_exists = await self._session.scalar(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id)
            )
            if workspace_exists is None:
                raise WorkspaceNotFoundError from exc
            raise
        return self._to_domain(model)

    async def get(self, project_id: UUID) -> Project | None:
        model = await self._session.get(ProjectModel, project_id)
        return self._to_domain(model) if model is not None else None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
    ) -> tuple[list[Project], int]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(ProjectModel)
            .where(ProjectModel.workspace_id == workspace_id)
        )
        models = await self._session.scalars(
            select(ProjectModel)
            .where(ProjectModel.workspace_id == workspace_id)
            .order_by(ProjectModel.created_at, ProjectModel.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [self._to_domain(model) for model in models], total or 0

    async def save(self, project_id: UUID, changes: ProjectChanges) -> Project | None:
        result = await self._session.execute(
            update(ProjectModel)
            .where(ProjectModel.id == project_id)
            .values(**changes)
            .returning(ProjectModel)
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def delete(self, project_id: UUID) -> bool:
        result = await self._session.execute(
            delete(ProjectModel)
            .where(ProjectModel.id == project_id)
            .returning(ProjectModel.id)
        )
        return result.scalar_one_or_none() is not None
