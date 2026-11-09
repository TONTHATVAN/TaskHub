from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authorization import ProjectAccess
from app.infrastructure.models import ProjectModel, WorkspaceMemberModel, WorkspaceModel


class SqlProjectAccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_access(
        self, project_id: UUID, user_id: UUID
    ) -> ProjectAccess | None:
        row = (
            await self._session.execute(
                select(WorkspaceModel.owner_id, WorkspaceMemberModel.role)
                .join(ProjectModel, ProjectModel.workspace_id == WorkspaceModel.id)
                .outerjoin(
                    WorkspaceMemberModel,
                    (WorkspaceMemberModel.workspace_id == WorkspaceModel.id)
                    & (WorkspaceMemberModel.user_id == user_id),
                )
                .where(ProjectModel.id == project_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return ProjectAccess(owner_id=row.owner_id, member_role=row.role)
