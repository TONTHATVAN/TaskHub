from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_task_repository
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository
from app.main import create_app


def create_test_app() -> FastAPI:
    app = create_app()
    repository = InMemoryTaskRepository()
    app.dependency_overrides[get_task_repository] = lambda: repository
    return app


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


def test_validation_project_scope_and_lifespan() -> None:
    project_id = uuid4()
    other_project_id = uuid4()
    app = create_test_app()

    with TestClient(app) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"
        assert client.post(endpoint, json={"title": "   "}).status_code == 422
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
        assert (
            client.patch(f"/api/v1/tasks/{task_id}", json={"title": "  "}).status_code
            == 422
        )
        assert client.get(f"/api/v1/tasks/{task_id}").json()["title"] == "Task"

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
        assert [item["title"] for item in first_page.json()] == ["Task 0", "Task 1"]
        assert [item["title"] for item in second_page.json()] == ["Task 2"]
        assert client.get(endpoint, params={"page": 0}).status_code == 422
