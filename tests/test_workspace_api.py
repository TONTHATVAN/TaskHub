import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.dependencies import get_current_user, get_workspace_repository
from app.application.tokens import JwtTokenService
from app.domain.user import User, UserRole
from app.domain.workspace import Workspace, WorkspaceRole
from app.infrastructure.database import engine, session_factory
from app.infrastructure.models import (
    ProjectModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from app.infrastructure.settings import settings
from app.main import create_app


def make_user(role: UserRole = UserRole.MEMBER) -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        full_name="Test User",
        hashed_password="disabled",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


class MemoryWorkspaceRepository:
    def __init__(self) -> None:
        self.workspaces: dict[UUID, Workspace] = {}

    async def add(self, name: str, owner_id: UUID) -> Workspace:
        workspace = Workspace(uuid4(), name, owner_id, datetime.now(UTC))
        self.workspaces[workspace.id] = workspace
        return workspace

    async def get(self, workspace_id: UUID) -> Workspace | None:
        return self.workspaces.get(workspace_id)

    async def rename(self, workspace_id: UUID, name: str) -> Workspace | None:
        old = self.workspaces.get(workspace_id)
        if old is None:
            return None
        updated = Workspace(old.id, name, old.owner_id, old.created_at)
        self.workspaces[workspace_id] = updated
        return updated

    async def delete(self, workspace_id: UUID) -> bool:
        return self.workspaces.pop(workspace_id, None) is not None


def test_workspace_crud_validation_and_owner_permissions() -> None:
    owner = make_user()
    other = make_user()
    admin = make_user(UserRole.ADMIN)
    current = [owner]
    repository = MemoryWorkspaceRepository()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current[0]
    app.dependency_overrides[get_workspace_repository] = lambda: repository

    with TestClient(app) as client:
        for name in ("  ", "x" * 201):
            assert (
                client.post("/api/v1/workspaces", json={"name": name}).status_code
                == 422
            )

        created = client.post("/api/v1/workspaces", json={"name": "  Team A  "})
        assert created.status_code == 201
        workspace_id = created.json()["id"]
        endpoint = f"/api/v1/workspaces/{workspace_id}"
        assert created.json()["name"] == "Team A"
        assert created.json()["owner_id"] == str(owner.id)
        assert client.get(endpoint).status_code == 200
        assert client.patch(endpoint, json={"name": None}).status_code == 422
        assert client.patch(endpoint, json={"name": " "}).status_code == 422
        assert client.get(endpoint).json()["name"] == "Team A"
        assert (
            client.post("/api/v1/workspaces", json={"name": "x" * 200}).status_code
            == 201
        )

        current[0] = other
        for response in (
            client.get(endpoint),
            client.patch(endpoint, json={"name": "Denied"}),
            client.delete(endpoint),
        ):
            assert response.status_code == 403
            assert response.json() == {"detail": "Insufficient permissions"}

        current[0] = admin
        assert client.get(endpoint).status_code == 200
        assert client.patch(endpoint, json={"name": "Admin edit"}).status_code == 200

        current[0] = owner
        assert client.get(endpoint).json()["name"] == "Admin edit"
        assert client.delete(endpoint).status_code == 204
        assert client.get(endpoint).json() == {"detail": "Workspace not found"}
        assert client.delete(endpoint).status_code == 404


def test_workspace_endpoints_require_token_and_document_errors() -> None:
    app = create_app()
    app.dependency_overrides[get_workspace_repository] = MemoryWorkspaceRepository
    paths = app.openapi()["paths"]
    for method in ("get", "patch", "delete"):
        operation = paths["/api/v1/workspaces/{workspace_id}"][method]
        assert "HTTPBearer" in operation["security"][0]
        assert {"401", "403", "404"} <= operation["responses"].keys()

    with TestClient(app) as client:
        workspace_id = uuid4()
        for response in (
            client.post("/api/v1/workspaces", json={"name": "Team"}),
            client.get(f"/api/v1/workspaces/{workspace_id}"),
            client.patch(f"/api/v1/workspaces/{workspace_id}", json={"name": "Team"}),
            client.delete(f"/api/v1/workspaces/{workspace_id}"),
        ):
            assert response.status_code == 401
            assert response.headers["WWW-Authenticate"] == "Bearer"


def test_workspace_disappearing_between_read_and_write_returns_404() -> None:
    owner = make_user()
    workspace_id = uuid4()

    class DisappearingWorkspaceRepository(MemoryWorkspaceRepository):
        async def rename(self, workspace_id: UUID, name: str) -> Workspace | None:
            return None

        async def delete(self, workspace_id: UUID) -> bool:
            return False

    repository = DisappearingWorkspaceRepository()
    repository.workspaces[workspace_id] = Workspace(
        workspace_id, "Original", owner.id, datetime.now(UTC)
    )
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_workspace_repository] = lambda: repository

    with TestClient(app) as client:
        endpoint = f"/api/v1/workspaces/{workspace_id}"
        for response in (
            client.patch(endpoint, json={"name": "Updated"}),
            client.delete(endpoint),
        ):
            assert response.status_code == 404
            assert response.json() == {"detail": "Workspace not found"}


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_workspace_postgres_owner_membership_and_cascade() -> None:
    asyncio.run(_exercise_workspace_postgres())


async def _exercise_workspace_postgres() -> None:
    owner_id, other_id = uuid4(), uuid4()
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
                        id=other_id,
                        email=f"other-{other_id}@example.invalid",
                        full_name="Other",
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
        other_headers = {"Authorization": f"Bearer {tokens.issue_access(other_id)}"}
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/workspaces",
                json={"name": "Database Team"},
                headers=owner_headers,
            )
            assert created.status_code == 201
            workspace_id = UUID(created.json()["id"])
            endpoint = f"/api/v1/workspaces/{workspace_id}"

            async with session_factory() as session:
                membership = await session.get(
                    WorkspaceMemberModel, (workspace_id, owner_id)
                )
                assert membership is not None
                assert membership.role == WorkspaceRole.OWNER
                project_id = uuid4()
                session.add(
                    ProjectModel(
                        id=project_id,
                        workspace_id=workspace_id,
                        name="Child project",
                    )
                )
                await session.commit()

            assert (
                await client.get(endpoint, headers=other_headers)
            ).status_code == 403
            assert (
                await client.patch(
                    endpoint, json={"name": "Denied"}, headers=other_headers
                )
            ).status_code == 403
            renamed = await client.patch(
                endpoint, json={"name": "Renamed"}, headers=owner_headers
            )
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "Renamed"
            assert (
                await client.delete(endpoint, headers=owner_headers)
            ).status_code == 204
            assert (
                await client.get(endpoint, headers=owner_headers)
            ).status_code == 404

            async with session_factory() as session:
                assert (
                    await session.get(WorkspaceMemberModel, (workspace_id, owner_id))
                    is None
                )
                assert await session.get(WorkspaceModel, workspace_id) is None
                assert await session.get(ProjectModel, project_id) is None
    finally:
        async with session_factory() as session:
            if workspace_id is not None:
                await session.execute(
                    delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
                )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_((owner_id, other_id)))
            )
            await session.commit()
        await engine.dispose()
