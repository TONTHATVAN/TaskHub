from uuid import UUID, uuid4

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.workspace import Workspace, WorkspaceRole
from app.infrastructure.models import WorkspaceMemberModel, WorkspaceModel


class SqlWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: WorkspaceModel) -> Workspace:
        return Workspace(
            id=model.id,
            name=model.name,
            owner_id=model.owner_id,
            created_at=model.created_at,
        )

    async def add(self, name: str, owner_id: UUID) -> Workspace:
        model = WorkspaceModel(id=uuid4(), name=name, owner_id=owner_id)
        self._session.add(model)
        await self._session.flush()
        self._session.add(
            WorkspaceMemberModel(
                workspace_id=model.id, user_id=owner_id, role=WorkspaceRole.OWNER
            )
        )
        await self._session.flush()
        return self._to_domain(model)

    async def get(self, workspace_id: UUID) -> Workspace | None:
        model = await self._session.get(WorkspaceModel, workspace_id)
        return self._to_domain(model) if model is not None else None

    async def rename(self, workspace_id: UUID, name: str) -> Workspace | None:
        result = await self._session.execute(
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .values(name=name)
            .returning(WorkspaceModel)
            .execution_options(populate_existing=True)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def delete(self, workspace_id: UUID) -> bool:
        result = await self._session.execute(
            delete(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .returning(WorkspaceModel.id)
        )
        return result.scalar_one_or_none() is not None
