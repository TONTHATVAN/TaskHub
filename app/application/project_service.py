from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import ProjectNotFoundError
from app.domain.project import Project, ProjectStatus
from app.domain.project_repository import ProjectChanges, ProjectRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def create(
        self, workspace_id: UUID, name: str, description: str | None
    ) -> Project:
        return await self._repository.add(workspace_id, name, description)

    async def get(self, project_id: UUID) -> Project:
        project = await self._repository.get(project_id)
        if project is None:
            raise ProjectNotFoundError
        return project

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
    ) -> list[Project]:
        return await self._repository.list_by_workspace(
            workspace_id, page=page, limit=limit
        )

    async def update(self, project_id: UUID, changes: ProjectChanges) -> Project:
        if not changes:
            return await self.get(project_id)
        project = await self._repository.save(project_id, changes)
        if project is None:
            raise ProjectNotFoundError
        return project

    async def archive(self, project_id: UUID) -> Project:
        return await self.update(project_id, {"status": ProjectStatus.ARCHIVED})

    async def delete(self, project_id: UUID) -> None:
        if not await self._repository.delete(project_id):
            raise ProjectNotFoundError
