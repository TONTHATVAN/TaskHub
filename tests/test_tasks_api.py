from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_task_authorization_service,
    get_task_repository,
)
from app.domain.authorization import ProjectAccess
from app.domain.exceptions import NotFoundError, ProjectNotFoundError, TaskNotFoundError
from app.domain.project import Project, ProjectStatus
from app.domain.task import Task
from app.domain.user import User, UserRole
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository
from app.main import create_app


def create_test_app() -> FastAPI:
    app = create_app()
    repository = InMemoryTaskRepository()
    app.dependency_overrides[get_task_repository] = lambda: repository
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid4(),
        email="test@example.com",
        full_name="Test",
        hashed_password="disabled",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_task_authorization_service] = lambda: AllowTaskAccess(
        repository
    )
    return app


class AllowTaskAccess:
    def __init__(self, repository: InMemoryTaskRepository) -> None:
        self.repository = repository

    async def require_project(
        self, user: User, project_id: UUID, *, write: bool
    ) -> ProjectAccess:
        return ProjectAccess(
            owner_id=user.id,
            member_role=None,
            project=Project(
                project_id,
                uuid4(),
                "Test project",
                None,
                ProjectStatus.ACTIVE,
                datetime.now(UTC),
            ),
        )

    async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
        task = await self.repository.get(task_id)
        if task is None:
            raise TaskNotFoundError
        return task


def test_task_handlers_reuse_authorized_task() -> None:
    class CountingTaskRepository(InMemoryTaskRepository):
        def __init__(self) -> None:
            super().__init__()
            self.get_calls = 0

        async def get(self, task_id: UUID) -> Task | None:
            self.get_calls += 1
            return await super().get(task_id)

    repository = CountingTaskRepository()
    app = create_test_app()
    app.dependency_overrides[get_task_repository] = lambda: repository
    app.dependency_overrides[get_task_authorization_service] = lambda: AllowTaskAccess(
        repository
    )

    with TestClient(app) as client:
        created = client.post(
            f"/api/v1/projects/{uuid4()}/tasks", json={"title": "One lookup"}
        )
        assert created.status_code == 201
        assert repository.get_calls == 0
        endpoint = f"/api/v1/tasks/{created.json()['id']}"
        assert client.get(endpoint).status_code == 200
        assert repository.get_calls == 1
        assert client.patch(endpoint, json={"title": "Updated"}).status_code == 200
        assert repository.get_calls == 2
        assert client.delete(endpoint).status_code == 204
        assert repository.get_calls == 3


def test_task_crud_flow() -> None:
    project_id = uuid4()
    app = create_test_app()

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

        created = client.post(
            f"/api/v1/projects/{project_id}/tasks",
            json={"title": "  Write API  ", "description": "First task"},
        )
        assert created.status_code == 201
        task = created.json()
        task_id = task["id"]
        assert task["title"] == "Write API"
        assert task["status"] == "TODO"
        assert task["priority"] == "MEDIUM"
        assert task["project_id"] == str(project_id)

        listed = client.get(f"/api/v1/projects/{project_id}/tasks")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [task_id]
        assert client.get(f"/api/v1/tasks/{task_id}").status_code == 200

        updated = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "IN_PROGRESS", "description": None},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "IN_PROGRESS"
        assert updated.json()["description"] is None
        assert updated.json()["title"] == "Write API"

        deleted = client.delete(f"/api/v1/tasks/{task_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/tasks/{task_id}").status_code == 404
        assert client.get(f"/api/v1/projects/{project_id}/tasks").json() == []


def test_task_assignment_due_date_and_filters() -> None:
    project_id = uuid4()
    assignee_id = uuid4()
    other_assignee_id = uuid4()
    repository = InMemoryTaskRepository()
    repository.assignable_users.add(assignee_id)
    app = create_test_app()
    app.dependency_overrides[get_task_repository] = lambda: repository
    app.dependency_overrides[get_task_authorization_service] = lambda: AllowTaskAccess(
        repository
    )
    endpoint = f"/api/v1/projects/{project_id}/tasks"
    due_date = "2026-12-01T09:00:00+07:00"

    with TestClient(app) as client:
        invalid = client.post(
            endpoint, json={"title": "Invalid", "assignee_id": str(other_assignee_id)}
        )
        assert invalid.status_code == 409
        assert invalid.json() == {
            "detail": "Assignee must be an active workspace member"
        }
        assert client.get(endpoint).json() == []
        assert (
            client.post(
                endpoint, json={"title": "Naive", "due_date": "2026-12-01T09:00:00"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint, json={"title": "Forged", "created_by": str(uuid4())}
            ).status_code
            == 422
        )

        assigned = client.post(
            endpoint,
            json={
                "title": "Assigned",
                "assignee_id": str(assignee_id),
                "due_date": due_date,
                "priority": "HIGH",
            },
        )
        assert assigned.status_code == 201
        task = assigned.json()
        assert task["assignee_id"] == str(assignee_id)
        assert datetime.fromisoformat(task["due_date"]).utcoffset() is not None
        assert task["created_by"] is not None
        unassigned = client.post(endpoint, json={"title": "Unassigned"})
        assert unassigned.status_code == 201

        for params in (
            {"assignee_id": str(assignee_id)},
            {"priority": "HIGH"},
            {"status": "TODO", "assignee_id": str(assignee_id), "limit": 1},
        ):
            listed = client.get(endpoint, params=params)
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [task["id"]]
        assert client.get(endpoint, params={"status": "INVALID"}).status_code == 422
        assert client.get(endpoint, params={"priority": "INVALID"}).status_code == 422
        assert client.get(endpoint, params={"assignee_id": "bad"}).status_code == 422

        task_endpoint = f"/api/v1/tasks/{task['id']}"
        failed_update = client.patch(
            task_endpoint,
            json={
                "assignee_id": str(other_assignee_id),
                "due_date": "2026-12-02T09:00:00+07:00",
            },
        )
        assert failed_update.status_code == 409
        unchanged = client.get(task_endpoint).json()
        assert unchanged["assignee_id"] == str(assignee_id)
        assert unchanged["due_date"] == task["due_date"]
        cleared = client.patch(
            task_endpoint, json={"assignee_id": None, "due_date": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["assignee_id"] is None
        assert cleared.json()["due_date"] is None
        assert (
            client.get(endpoint, params={"assignee_id": str(assignee_id)}).json() == []
        )


def test_validation_project_scope_and_lifespan() -> None:
    project_id = uuid4()
    other_project_id = uuid4()
    app = create_test_app()

    with TestClient(app) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"
        assert client.post(endpoint, json={"title": "   "}).status_code == 422
        assert (
            client.post(
                endpoint, json={"title": "Task", "assignee_id": str(uuid4())}
            ).status_code
            == 409
        )
        assert client.post(endpoint, json={"title": None}).status_code == 422
        assert client.post(endpoint, json={"title": "x" * 201}).status_code == 422
        assert (
            client.post(
                "/api/v1/projects/not-a-uuid/tasks", json={"title": "Task"}
            ).status_code
            == 422
        )

        created = client.post(endpoint, json={"title": "Task"})
        task_id = created.json()["id"]
        assert client.get(f"/api/v1/projects/{other_project_id}/tasks").json() == []
        assert (
            client.patch(f"/api/v1/tasks/{task_id}", json={"status": None}).status_code
            == 422
        )
        null_title = client.patch(f"/api/v1/tasks/{task_id}", json={"title": None})
        assert null_title.status_code == 422
        assert "This field cannot be null" in null_title.json()["detail"][0]["msg"]
        assert (
            client.patch(
                f"/api/v1/tasks/{task_id}", json={"priority": None}
            ).status_code
            == 422
        )
        assert (
            client.patch(f"/api/v1/tasks/{task_id}", json={"title": "  "}).status_code
            == 422
        )
        assert client.get(f"/api/v1/tasks/{task_id}").json()["title"] == "Task"
        assert client.get(endpoint).json()[0]["title"] == "Task"

        assert client.post(endpoint, json={"title": "x" * 200}).status_code == 201

    with TestClient(app) as client:
        assert client.get(f"/api/v1/tasks/{task_id}").status_code == 200


def test_task_pagination() -> None:
    project_id = uuid4()
    with TestClient(create_test_app()) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"
        for index in range(3):
            assert (
                client.post(endpoint, json={"title": f"Task {index}"}).status_code
                == 201
            )

        first_page = client.get(endpoint, params={"page": 1, "limit": 2})
        second_page = client.get(endpoint, params={"page": 2, "limit": 2})
        first_titles = {item["title"] for item in first_page.json()}
        second_titles = {item["title"] for item in second_page.json()}
        assert len(first_titles) == 2
        assert len(second_titles) == 1
        assert first_titles.isdisjoint(second_titles)
        assert first_titles | second_titles == {"Task 0", "Task 1", "Task 2"}
        assert (
            client.get(endpoint, params={"page": 1, "limit": 2}).json()
            == first_page.json()
        )
        assert client.get(endpoint, params={"page": 0}).status_code == 422
        assert client.get(endpoint, params={"limit": 0}).status_code == 422
        assert client.get(endpoint, params={"limit": 101}).status_code == 422
        assert client.get(endpoint, params={"limit": 100}).status_code == 200
        assert len(client.get(endpoint).json()) == 3


def test_default_task_page_size() -> None:
    project_id = uuid4()
    with TestClient(create_test_app()) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"
        for index in range(21):
            assert (
                client.post(endpoint, json={"title": f"Task {index}"}).status_code
                == 201
            )

        assert len(client.get(endpoint).json()) == 20
        assert len(client.get(endpoint, params={"page": 2}).json()) == 1


def test_not_found_responses() -> None:
    app = create_test_app()
    missing_task_id = uuid4()

    with TestClient(app) as client:
        for response in (
            client.get(f"/api/v1/tasks/{missing_task_id}"),
            client.patch(f"/api/v1/tasks/{missing_task_id}", json={"title": "Task"}),
            client.delete(f"/api/v1/tasks/{missing_task_id}"),
        ):
            assert response.status_code == 404
            assert response.json() == {"detail": "Task not found"}

    class MissingProjectAccess(AllowTaskAccess):
        async def require_project(
            self, user: User, project_id: UUID, *, write: bool
        ) -> ProjectAccess:
            raise ProjectNotFoundError

    app.dependency_overrides[get_task_authorization_service] = lambda: (
        MissingProjectAccess(InMemoryTaskRepository())
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/projects/{uuid4()}/tasks", json={"title": "Task"}
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found"}


def test_not_found_handler_uses_exception_message() -> None:
    app = create_test_app()

    @app.get("/test/missing")
    async def missing() -> None:
        raise NotFoundError("Custom resource not found")

    with TestClient(app) as client:
        response = client.get("/test/missing")
        assert response.status_code == 404
        assert response.json() == {"detail": "Custom resource not found"}


def test_task_not_found_responses_are_documented() -> None:
    paths = create_test_app().openapi()["paths"]
    for method in ("get", "patch", "delete"):
        response = paths["/api/v1/tasks/{task_id}"][method]["responses"]["404"]
        assert response["description"] == "Task not found"
        assert response["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorRead"
        }

    response = paths["/api/v1/projects/{project_id}/tasks"]["post"]["responses"]["404"]
    assert response["description"] == "Project not found"
    for operation in (
        paths["/api/v1/projects/{project_id}/tasks"]["post"],
        paths["/api/v1/tasks/{task_id}"]["patch"],
    ):
        assert operation["responses"]["409"]["description"] == (
            "Project is archived; Assignee must be an active workspace member"
        )
        assert "422" in operation["responses"]
