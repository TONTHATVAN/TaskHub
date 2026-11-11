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

from app.api.dependencies import (
    get_current_user,
    get_user_repository,
    get_workspace_repository,
)
from app.application.tokens import JwtTokenService
from app.application.workspace_service import WorkspaceService
from app.domain.exceptions import WorkspaceNotFoundError
from app.domain.user import User, UserRole
from app.domain.workspace import Workspace, WorkspaceMember, WorkspaceRole
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
        self.members: dict[tuple[UUID, UUID], WorkspaceRole] = {}

    async def add(self, name: str, owner_id: UUID) -> Workspace:
        workspace = Workspace(uuid4(), name, owner_id, datetime.now(UTC))
        self.workspaces[workspace.id] = workspace
        self.members[workspace.id, owner_id] = WorkspaceRole.OWNER
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
        if self.workspaces.pop(workspace_id, None) is None:
            return False
        self.members = {
            key: role for key, role in self.members.items() if key[0] != workspace_id
        }
        return True

    async def get_member_role(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceRole | None:
        return self.members.get((workspace_id, user_id))

    async def list_members(self, workspace_id: UUID) -> list[WorkspaceMember]:
        return [
            WorkspaceMember(user_id, role)
            for (stored_workspace_id, user_id), role in self.members.items()
            if stored_workspace_id == workspace_id
        ]

    async def add_member(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool:
        if (workspace_id, user_id) in self.members:
            return False
        self.members[workspace_id, user_id] = role
        return True

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        role = self.members.get((workspace_id, user_id))
        if role is None or role is WorkspaceRole.OWNER:
            return False
        del self.members[workspace_id, user_id]
        return True


def test_removed_workspace_reports_workspace_not_found() -> None:
    class DeletedWorkspaceRepository(MemoryWorkspaceRepository):
        async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
            self.workspaces.pop(workspace_id, None)
            return False

    async def exercise() -> None:
        owner = make_user()
        member = make_user()
        repository = DeletedWorkspaceRepository()
        workspace = await repository.add("Team", owner.id)
        service = WorkspaceService(repository, MemoryUserRepository())
        with pytest.raises(WorkspaceNotFoundError):
            await service.remove_member(owner, workspace.id, member.id)

    asyncio.run(exercise())


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


def test_workspace_members_and_role_boundaries() -> None:
    owner, editor, viewer, outsider = (make_user() for _ in range(4))
    admin = make_user(UserRole.ADMIN)
    current = [owner]
    repository = MemoryWorkspaceRepository()
    users = MemoryUserRepository()
    users.users = {
        user.email: user for user in (owner, editor, viewer, outsider, admin)
    }
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current[0]
    app.dependency_overrides[get_workspace_repository] = lambda: repository
    app.dependency_overrides[get_user_repository] = lambda: users

    with TestClient(app) as client:
        created = client.post("/api/v1/workspaces", json={"name": "Team"})
        workspace = f"/api/v1/workspaces/{created.json()['id']}"
        members = f"{workspace}/members"
        assert created.status_code == 201
        assert (
            client.post(
                "/api/v1/workspaces",
                json={"name": "Injected", "owner_id": str(outsider.id)},
            ).status_code
            == 422
        )

        invite_editor = client.post(
            members, json={"user_id": str(editor.id), "role": "EDITOR"}
        )
        assert invite_editor.status_code == 201
        assert invite_editor.json() == {"user_id": str(editor.id), "role": "EDITOR"}
        duplicate = client.post(
            members, json={"user_id": str(editor.id), "role": "EDITOR"}
        )
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "User is already a workspace member"}
        assert (
            client.post(
                members, json={"user_id": str(viewer.id), "role": "OWNER"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                members, json={"user_id": str(uuid4()), "role": "VIEWER"}
            ).status_code
            == 404
        )
        inactive = replace(outsider, is_active=False)
        users.users[outsider.email] = inactive
        inactive_invite = client.post(
            members, json={"user_id": str(outsider.id), "role": "VIEWER"}
        )
        assert inactive_invite.status_code == 409
        assert inactive_invite.json() == {
            "detail": "Inactive user cannot join workspace"
        }
        users.users[outsider.email] = outsider
        assert (
            client.post(
                members, json={"user_id": str(viewer.id), "role": "VIEWER"}
            ).status_code
            == 201
        )
        assert {row["user_id"] for row in client.get(members).json()} == {
            str(owner.id),
            str(editor.id),
            str(viewer.id),
        }

        for member in (editor, viewer):
            current[0] = member
            assert client.get(workspace).status_code == 200
            assert client.get(members).status_code == 200
            assert client.patch(workspace, json={"name": "Denied"}).status_code == 403
            assert client.delete(workspace).status_code == 403
            assert (
                client.post(
                    members, json={"user_id": str(outsider.id), "role": "EDITOR"}
                ).status_code
                == 403
            )
            assert client.delete(f"{members}/{editor.id}").status_code == 403

        current[0] = outsider
        assert client.get(workspace).status_code == 403
        assert client.get(members).status_code == 403

        current[0] = owner
        assert client.delete(f"{members}/{owner.id}").status_code == 403
        assert client.delete(f"{members}/{outsider.id}").status_code == 404
        assert client.delete(f"{members}/{editor.id}").status_code == 204
        assert client.delete(f"{members}/{editor.id}").status_code == 404
        current[0] = editor
        assert client.get(workspace).status_code == 403
        current[0] = admin
        assert client.get(members).status_code == 200
        assert client.delete(f"{members}/{viewer.id}").status_code == 204


def test_workspace_endpoints_require_token_and_document_errors() -> None:
    app = create_app()
    app.dependency_overrides[get_workspace_repository] = MemoryWorkspaceRepository
    paths = app.openapi()["paths"]
    for method in ("get", "patch", "delete"):
        operation = paths["/api/v1/workspaces/{workspace_id}"][method]
        assert "HTTPBearer" in operation["security"][0]
        assert {"401", "403", "404"} <= operation["responses"].keys()
    for method in ("get", "post"):
        operation = paths["/api/v1/workspaces/{workspace_id}/members"][method]
        assert "HTTPBearer" in operation["security"][0]
        assert {"401", "403", "404"} <= operation["responses"].keys()
    assert (
        "409" in paths["/api/v1/workspaces/{workspace_id}/members"]["post"]["responses"]
    )
    assert (
        paths["/api/v1/workspaces/{workspace_id}"]["get"]["responses"]["404"][
            "description"
        ]
        == "Workspace not found"
    )
    assert {"401", "403", "404"} <= paths[
        "/api/v1/workspaces/{workspace_id}/members/{member_id}"
    ]["delete"]["responses"].keys()

    with TestClient(app) as client:
        workspace_id = uuid4()
        for response in (
            client.post("/api/v1/workspaces", json={"name": "Team"}),
            client.get(f"/api/v1/workspaces/{workspace_id}"),
            client.patch(f"/api/v1/workspaces/{workspace_id}", json={"name": "Team"}),
            client.delete(f"/api/v1/workspaces/{workspace_id}"),
            client.get(f"/api/v1/workspaces/{workspace_id}/members"),
            client.post(
                f"/api/v1/workspaces/{workspace_id}/members",
                json={"user_id": str(uuid4()), "role": "EDITOR"},
            ),
            client.delete(f"/api/v1/workspaces/{workspace_id}/members/{uuid4()}"),
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
            members_endpoint = f"{endpoint}/members"

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
            invited = await client.post(
                members_endpoint,
                json={"user_id": str(other_id), "role": "VIEWER"},
                headers=owner_headers,
            )
            assert invited.status_code == 201
            assert (
                await client.post(
                    members_endpoint,
                    json={"user_id": str(other_id), "role": "VIEWER"},
                    headers=owner_headers,
                )
            ).status_code == 409
            async with session_factory() as session:
                membership = await session.get(
                    WorkspaceMemberModel, (workspace_id, other_id)
                )
                assert membership is not None
                assert membership.role == WorkspaceRole.VIEWER
            assert (
                await client.get(endpoint, headers=other_headers)
            ).status_code == 200
            assert (
                await client.patch(
                    endpoint, json={"name": "Denied"}, headers=other_headers
                )
            ).status_code == 403
            assert (
                await client.delete(
                    f"{members_endpoint}/{owner_id}", headers=owner_headers
                )
            ).status_code == 403
            assert (
                await client.delete(
                    f"{members_endpoint}/{other_id}", headers=owner_headers
                )
            ).status_code == 204
            assert (
                await client.get(endpoint, headers=other_headers)
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
