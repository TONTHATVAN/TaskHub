from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import UserNotFoundError, WorkspaceNotFoundError
from app.domain.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.infrastructure.models import (
    ProjectModel,
    TaskModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)


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

    async def get_member_role(
        self, workspace_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> WorkspaceRole | None:
        statement = select(WorkspaceMemberModel.role).where(
            WorkspaceMemberModel.workspace_id == workspace_id,
            WorkspaceMemberModel.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update(read=True, of=WorkspaceMemberModel)
        return await self._session.scalar(statement)

    async def list_members(
        self,
        workspace_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
    ) -> tuple[list[WorkspaceMember], int]:
        total = await self._session.scalar(
            select(func.count())
            .select_from(WorkspaceMemberModel)
            .where(WorkspaceMemberModel.workspace_id == workspace_id)
        )
        rows = await self._session.execute(
            select(WorkspaceMemberModel.user_id, WorkspaceMemberModel.role)
            .where(WorkspaceMemberModel.workspace_id == workspace_id)
            .order_by(WorkspaceMemberModel.user_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [WorkspaceMember(row.user_id, row.role) for row in rows], total or 0

    async def add_member(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool:
        try:
            async with self._session.begin_nested():
                result = await self._session.execute(
                    insert(WorkspaceMemberModel)
                    .values(workspace_id=workspace_id, user_id=user_id, role=role)
                    .on_conflict_do_nothing()
                    .returning(WorkspaceMemberModel.user_id)
                )
        except IntegrityError as exc:
            workspace_exists = await self._session.scalar(
                select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id)
            )
            if workspace_exists is None:
                raise WorkspaceNotFoundError from exc
            user_exists = await self._session.scalar(
                select(UserModel.id).where(UserModel.id == user_id)
            )
            if user_exists is None:
                raise UserNotFoundError from exc
            raise
        return result.scalar_one_or_none() is not None

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        result = await self._session.execute(
            delete(WorkspaceMemberModel)
            .where(
                WorkspaceMemberModel.workspace_id == workspace_id,
                WorkspaceMemberModel.user_id == user_id,
                WorkspaceMemberModel.role != WorkspaceRole.OWNER,
            )
            .returning(WorkspaceMemberModel.user_id)
        )
        if result.scalar_one_or_none() is None:
            return False
        await self._session.execute(
            update(TaskModel)
            .where(
                TaskModel.assignee_id == user_id,
                TaskModel.project_id.in_(
                    select(ProjectModel.id).where(
                        ProjectModel.workspace_id == workspace_id
                    )
                ),
            )
            .values(assignee_id=None)
        )
        return True
