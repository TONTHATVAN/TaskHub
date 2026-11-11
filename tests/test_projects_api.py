import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from test_auth_api import MemoryUserRepository
from test_workspace_api import MemoryWorkspaceRepository, make_user

from app.api.dependencies import (
    get_current_user,
    get_project_access_repository,
    get_project_repository,
    get_user_repository,
    get_workspace_repository,
)
from app.application.tokens import JwtTokenService
from app.domain.authorization import ProjectAccess
from app.domain.exceptions import UserNotFoundError, WorkspaceNotFoundError
from app.domain.project import Project, ProjectStatus
from app.domain.project_repository import ProjectChanges
from app.domain.user import UserRole
from app.domain.workspace import WorkspaceRole
from app.infrastructure.database import engine, session_factory
from app.infrastructure.models import ProjectModel, TaskModel, UserModel, WorkspaceModel
from app.infrastructure.repositories.project import SqlProjectRepository
from app.infrastructure.repositories.workspace import SqlWorkspaceRepository
from app.infrastructure.settings import settings
from app.main import create_app


class MemoryProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}

    async def add(
        self, workspace_id: UUID, name: str, description: str | None
    ) -> Project:
        project = Project(
            uuid4(),
            workspace_id,
            name,
            description,
            ProjectStatus.ACTIVE,
            datetime.now(UTC),
        )
        self.projects[project.id] = project
        return project

    async def get(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    async def list_by_workspace(
        self, workspace_id: UUID, *, page: int = 1, limit: int = 20
    ) -> list[Project]:
        projects = sorted(
            (p for p in self.projects.values() if p.workspace_id == workspace_id),
            key=lambda p: (p.created_at, p.id),
        )
        return projects[(page - 1) * limit : page * limit]

    async def save(self, project_id: UUID, changes: ProjectChanges) -> Project | None:
        project = self.projects.get(project_id)
        if project is None:
            return None
        updated = replace(project, **changes)
        self.projects[project_id] = updated
        return updated

    async def delete(self, project_id: UUID) -> bool:
        return self.projects.pop(project_id, None) is not None


class MemoryProjectAccessRepository:
    def __init__(
        self, projects: MemoryProjectRepository, workspaces: MemoryWorkspaceRepository
    ) -> None:
        self.projects = projects
        self.workspaces = workspaces

    async def get_project_access(
        self, project_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> ProjectAccess | None:
        project = self.projects.projects.get(project_id)
        if project is None:
            return None
        workspace = self.workspaces.workspaces.get(project.workspace_id)
        if workspace is None:
            return None
        role = self.workspaces.members.get((workspace.id, user_id))
        return ProjectAccess(workspace.owner_id, role, project.status)


def test_project_crud_archive_and_role_permissions() -> None:
    owner, editor, viewer, outsider = (make_user() for _ in range(4))
    admin = make_user(UserRole.ADMIN)
    current = [owner]
    workspaces = MemoryWorkspaceRepository()
    projects = MemoryProjectRepository()
    users = MemoryUserRepository()
    users.users = {
        user.email: user for user in (owner, editor, viewer, outsider, admin)
    }
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current[0]
    app.dependency_overrides[get_workspace_repository] = lambda: workspaces
    app.dependency_overrides[get_project_repository] = lambda: projects
    app.dependency_overrides[get_project_access_repository] = lambda: (
        MemoryProjectAccessRepository(projects, workspaces)
    )
    app.dependency_overrides[get_user_repository] = lambda: users

    with TestClient(app) as client:
        workspace_id = client.post(
            "/api/v1/workspaces", json={"name": "Project team"}
        ).json()["id"]
        workspace_path = f"/api/v1/workspaces/{workspace_id}"
        collection = f"{workspace_path}/projects"
        for name in ("  ", "x" * 201):
            assert client.post(collection, json={"name": name}).status_code == 422
        assert (
            client.post(
                collection, json={"name": "Injected", "status": "ARCHIVED"}
            ).status_code
            == 422
        )
        created = client.post(
            collection, json={"name": "  Project A  ", "description": "First"}
        )
        assert created.status_code == 201
        assert created.json()["name"] == "Project A"
        assert created.json()["status"] == "ACTIVE"
        project = f"/api/v1/projects/{created.json()['id']}"
        assert client.get(project).status_code == 200
        assert len(client.get(collection).json()) == 1
        assert client.get(f"{collection}?page=0").status_code == 422
        assert client.get(f"{collection}?limit=101").status_code == 422
        assert client.patch(project, json={"name": None}).status_code == 422
        assert client.patch(project, json={"name": " "}).status_code == 422
        assert (
            client.patch(project, json={"description": None}).json()["description"]
            is None
        )

        workspaces.members[UUID(workspace_id), editor.id] = WorkspaceRole.EDITOR
        workspaces.members[UUID(workspace_id), viewer.id] = WorkspaceRole.VIEWER
        current[0] = viewer
        assert client.get(collection).status_code == 200
        assert client.get(project).status_code == 200
        assert client.post(collection, json={"name": "Denied"}).status_code == 403
        assert client.patch(project, json={"name": "Denied"}).status_code == 403
        assert client.post(f"{project}/archive").status_code == 403
        assert client.delete(project).status_code == 403

        current[0] = outsider
        assert client.get(collection).status_code == 403
        assert client.get(project).status_code == 403
        current[0] = editor
        assert client.post(collection, json={"name": "Project B"}).status_code == 201
        assert client.patch(project, json={"name": "Edited"}).json()["name"] == "Edited"
        archived = client.post(f"{project}/archive")
        assert archived.status_code == 200
        assert archived.json()["status"] == "ARCHIVED"
        assert client.post(f"{project}/archive").status_code == 200
        assert client.patch(project, json={"name": "Blocked"}).status_code == 409
        blocked_task = client.post(f"{project}/tasks", json={"title": "Blocked"})
        assert blocked_task.status_code == 409
        assert blocked_task.json() == {"detail": "Project is archived"}
        assert client.get(project).json()["name"] == "Edited"
        assert client.delete(project).status_code == 204
        assert client.get(project).status_code == 404

        current[0] = admin
        assert client.get(collection).status_code == 200
        assert (
            client.post(collection, json={"name": "Admin project"}).status_code == 201
        )


def test_project_routes_document_authorization_errors() -> None:
    app = create_app()
    paths = app.openapi()["paths"]
    for path, method in (
        ("/api/v1/workspaces/{workspace_id}/projects", "post"),
        ("/api/v1/workspaces/{workspace_id}/projects", "get"),
        ("/api/v1/projects/{project_id}", "get"),
        ("/api/v1/projects/{project_id}", "patch"),
        ("/api/v1/projects/{project_id}", "delete"),
        ("/api/v1/projects/{project_id}/archive", "post"),
    ):
        operation = paths[path][method]
        assert "HTTPBearer" in operation["security"][0]
        assert {"401", "403", "404"} <= operation["responses"].keys()
    assert (
        paths["/api/v1/projects/{project_id}"]["get"]["responses"]["404"]["description"]
        == "Project not found"
    )
    assert (
        paths["/api/v1/projects/{project_id}"]["patch"]["responses"]["409"][
            "description"
        ]
        == "Project is archived"
    )


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_project_postgres_persistence_and_archive() -> None:
    asyncio.run(_exercise_project_postgres())


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_missing_workspace_or_user_during_insert_returns_404() -> None:
    asyncio.run(_exercise_missing_parent_inserts())


async def _exercise_missing_parent_inserts() -> None:
    owner_id, workspace_id = uuid4(), uuid4()
    try:
        async with session_factory() as session:
            with pytest.raises(WorkspaceNotFoundError):
                await SqlProjectRepository(session).add(workspace_id, "Missing", None)
            with pytest.raises(WorkspaceNotFoundError):
                await SqlWorkspaceRepository(session).add_member(
                    workspace_id, uuid4(), WorkspaceRole.EDITOR
                )
            session.add(
                UserModel(
                    id=owner_id,
                    email=f"owner-{owner_id}@example.invalid",
                    full_name="Owner",
                    hashed_password="disabled",
                )
            )
            session.add(
                WorkspaceModel(id=workspace_id, name="Present", owner_id=owner_id)
            )
            await session.commit()

        async with session_factory() as session:
            with pytest.raises(UserNotFoundError):
                await SqlWorkspaceRepository(session).add_member(
                    workspace_id, uuid4(), WorkspaceRole.EDITOR
                )
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
            )
            await session.execute(delete(UserModel).where(UserModel.id == owner_id))
            await session.commit()
        await engine.dispose()


async def _exercise_project_postgres() -> None:
    owner_id, viewer_id = uuid4(), uuid4()
    workspace_id: UUID | None = None
    try:
        async with session_factory() as session:
            session.add_all(
                (
                    UserModel(
                        id=owner_id,
                        email=f"owner-{owner_id}@example.invalid",
                        full_name="Owner",
                        hashed_password="disabled",
                    ),
                    UserModel(
                        id=viewer_id,
                        email=f"viewer-{viewer_id}@example.invalid",
                        full_name="Viewer",
                        hashed_password="disabled",
                    ),
                )
            )
            await session.commit()
        tokens = JwtTokenService(
            settings.jwt_secret_key.get_secret_value(),
            settings.jwt_access_minutes,
            settings.jwt_refresh_days,
        )
        owner_headers = {"Authorization": f"Bearer {tokens.issue_access(owner_id)}"}
        viewer_headers = {"Authorization": f"Bearer {tokens.issue_access(viewer_id)}"}
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            workspace = await client.post(
                "/api/v1/workspaces",
                json={"name": "Database team"},
                headers=owner_headers,
            )
            assert workspace.status_code == 201
            workspace_id = UUID(workspace.json()["id"])
            collection = f"/api/v1/workspaces/{workspace_id}/projects"
            created = await client.post(
                collection,
                json={"name": "First", "description": "Text"},
                headers=owner_headers,
            )
            assert created.status_code == 201
            project_id = UUID(created.json()["id"])
            project = f"/api/v1/projects/{project_id}"
            assert (
                await client.get(project, headers=viewer_headers)
            ).status_code == 403
            assert (
                await client.post(
                    f"/api/v1/workspaces/{workspace_id}/members",
                    json={"user_id": str(viewer_id), "role": "VIEWER"},
                    headers=owner_headers,
                )
            ).status_code == 201
            assert (
                await client.get(project, headers=viewer_headers)
            ).status_code == 200
            assert (
                await client.patch(
                    project, json={"name": "Denied"}, headers=viewer_headers
                )
            ).status_code == 403
            updated = await client.patch(
                project, json={"description": None}, headers=owner_headers
            )
            assert updated.status_code == 200
            assert updated.json()["description"] is None
            task = await client.post(
                f"{project}/tasks",
                json={"title": "Existing task"},
                headers=owner_headers,
            )
            assert task.status_code == 201
            task_id = UUID(task.json()["id"])
            archived = await client.post(f"{project}/archive", headers=owner_headers)
            assert archived.status_code == 200
            async with session_factory() as session:
                stored = await session.get(ProjectModel, project_id)
                assert stored is not None
                assert stored.status == ProjectStatus.ARCHIVED
                assert stored.description is None
            assert (
                await client.post(
                    f"{project}/tasks",
                    json={"title": "Blocked"},
                    headers=owner_headers,
                )
            ).status_code == 409
            assert (
                await client.patch(
                    f"/api/v1/tasks/{task_id}",
                    json={"title": "Blocked"},
                    headers=owner_headers,
                )
            ).status_code == 409
            assert (
                await client.get(f"/api/v1/tasks/{task_id}", headers=owner_headers)
            ).status_code == 200
            assert (
                await client.delete(project, headers=owner_headers)
            ).status_code == 204
            assert (await client.get(project, headers=owner_headers)).status_code == 404
            async with session_factory() as session:
                assert await session.get(TaskModel, task_id) is None
    finally:
        async with session_factory() as session:
            if workspace_id is not None:
                await session.execute(
                    delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
                )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_id, viewer_id)))
            )
            await session.commit()
        await engine.dispose()
