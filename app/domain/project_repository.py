from typing import Protocol, TypedDict
from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.project import Project, ProjectStatus


class ProjectChanges(TypedDict, total=False):
    name: str
    description: str | None
    status: ProjectStatus


class ProjectRepository(Protocol):
    async def add(
        self, workspace_id: UUID, name: str, description: str | None
    ) -> Project: ...

    async def get(self, project_id: UUID) -> Project | None: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        page: int = PAGE_DEFAULT,
        limit: int = LIMIT_DEFAULT,
    ) -> list[Project]: ...

    async def save(
        self, project_id: UUID, changes: ProjectChanges
    ) -> Project | None: ...

    async def delete(self, project_id: UUID) -> bool: ...
