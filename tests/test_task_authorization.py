from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_project_access_repository,
    get_task_repository,
)
from app.domain.authorization import ProjectAccess
from app.domain.project import Project, ProjectStatus
from app.domain.user import User, UserRole
from app.domain.workspace import WorkspaceRole
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository
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


class MemoryProjectAccessRepository:
    def __init__(self, project_id: UUID, owner_id: UUID) -> None:
        self.project_id = project_id
        self.owner_id = owner_id
        self.members: dict[UUID, WorkspaceRole] = {}

    async def get_project_access(
        self, project_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> ProjectAccess | None:
        if project_id != self.project_id:
            return None
        return ProjectAccess(
            self.owner_id,
            self.members.get(user_id),
            Project(
                project_id,
                uuid4(),
                "Test project",
                None,
                ProjectStatus.ACTIVE,
                datetime.now(UTC),
            ),
        )


def test_task_permissions_follow_workspace_roles() -> None:
    project_id = uuid4()
    owner = make_user()
    editor = make_user()
    viewer = make_user()
    outsider = make_user()
    admin = make_user(UserRole.ADMIN)
    access = MemoryProjectAccessRepository(project_id, owner.id)
    access.members[editor.id] = WorkspaceRole.EDITOR
    access.members[viewer.id] = WorkspaceRole.VIEWER
    current = [owner]
    app = create_app()
    tasks = InMemoryTaskRepository()
    app.dependency_overrides[get_task_repository] = lambda: tasks
    app.dependency_overrides[get_project_access_repository] = lambda: access
    app.dependency_overrides[get_current_user] = lambda: current[0]

    with TestClient(app) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"
        created = client.post(endpoint, json={"title": "Protected"})
        assert created.status_code == 201
        task_id = created.json()["id"]
        task_endpoint = f"/api/v1/tasks/{task_id}"

        current[0] = viewer
        assert client.get(endpoint).status_code == 200
        assert client.get(task_endpoint).status_code == 200
        for response in (
            client.post(endpoint, json={"title": "Denied"}),
            client.patch(task_endpoint, json={"title": "Denied"}),
            client.delete(task_endpoint),
        ):
            assert response.status_code == 403
            assert response.json() == {"detail": "Insufficient permissions"}
        assert client.get(task_endpoint).json()["title"] == "Protected"

        current[0] = outsider
        assert client.get(endpoint).status_code == 404
        assert client.get(task_endpoint).status_code == 404
        assert client.post(endpoint, json={"title": "Denied"}).status_code == 404

        current[0] = editor
        assert client.patch(task_endpoint, json={"title": "Edited"}).status_code == 200
        assert client.post(endpoint, json={"title": "Second"}).status_code == 201

        current[0] = admin
        assert client.get(task_endpoint).status_code == 200
        assert client.delete(task_endpoint).status_code == 204

        current[0] = owner
        assert client.get(f"/api/v1/projects/{uuid4()}/tasks").status_code == 404
        assert client.get(task_endpoint).status_code == 404


def test_task_endpoints_require_access_token() -> None:
    app = create_app()
    app.dependency_overrides[get_task_repository] = InMemoryTaskRepository
    app.dependency_overrides[get_project_access_repository] = lambda: (
        MemoryProjectAccessRepository(uuid4(), uuid4())
    )
    with TestClient(app) as client:
        project_id = uuid4()
        task_id = uuid4()
        for response in (
            client.post(f"/api/v1/projects/{project_id}/tasks", json={"title": "Task"}),
            client.get(f"/api/v1/projects/{project_id}/tasks"),
            client.get(f"/api/v1/tasks/{task_id}"),
            client.patch(f"/api/v1/tasks/{task_id}", json={"title": "Task"}),
            client.delete(f"/api/v1/tasks/{task_id}"),
        ):
            assert response.status_code == 401
            assert response.headers["WWW-Authenticate"] == "Bearer"


def test_task_permissions_are_documented() -> None:
    paths = create_app().openapi()["paths"]
    for endpoint, methods in (
        ("/api/v1/projects/{project_id}/tasks", ("get", "post")),
        ("/api/v1/tasks/{task_id}", ("get", "patch", "delete")),
    ):
        for method in methods:
            operation = paths[endpoint][method]
            assert "HTTPBearer" in operation["security"][0]
            assert "401" in operation["responses"]
            assert "403" in operation["responses"]
