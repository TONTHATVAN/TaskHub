from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authorization import ProjectAccess
from app.domain.workspace import WorkspaceRole
from app.infrastructure.models import ProjectModel, WorkspaceMemberModel, WorkspaceModel
from app.infrastructure.repositories.project import SqlProjectRepository


class SqlProjectAccessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_access(
        self, project_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> ProjectAccess | None:
        statement = (
            select(
                ProjectModel,
                WorkspaceModel.id,
                WorkspaceModel.owner_id,
                WorkspaceMemberModel.role,
            )
            .join(WorkspaceModel, ProjectModel.workspace_id == WorkspaceModel.id)
            .outerjoin(
                WorkspaceMemberModel,
                (WorkspaceMemberModel.workspace_id == WorkspaceModel.id)
                & (WorkspaceMemberModel.user_id == user_id),
            )
            .where(ProjectModel.id == project_id)
        )
        if for_update:
            statement = statement.with_for_update(of=ProjectModel)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        member_role: WorkspaceRole | None = row[3]
        if for_update and member_role is not None:
            member_role = await self._session.scalar(
                select(WorkspaceMemberModel.role)
                .where(
                    WorkspaceMemberModel.workspace_id == row[1],
                    WorkspaceMemberModel.user_id == user_id,
                )
                .with_for_update(read=True, of=WorkspaceMemberModel)
            )
        return ProjectAccess(
            owner_id=row[2],
            member_role=member_role,
            project=SqlProjectRepository._to_domain(row[0]),
        )
