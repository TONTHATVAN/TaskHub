import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.infrastructure.database import engine, session_factory
from app.infrastructure.models import ProjectModel, UserModel, WorkspaceModel
from app.infrastructure.repositories.base import BaseRepository
from app.main import create_app


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_task_crud_and_persistence() -> None:
    asyncio.run(_exercise_database())


async def _exercise_database() -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()

    try:
        async with session_factory() as session:
            user = UserModel(
                id=user_id,
                email=f"integration-{user_id}@example.invalid",
                full_name="Integration Test",
                hashed_password="disabled",
            )
            workspace = WorkspaceModel(id=workspace_id, name="Integration", owner=user)
            project = ProjectModel(id=project_id, name="Integration", workspace=workspace)
            await BaseRepository(session, UserModel).add(user)
            session.add(project)
            await session.commit()

        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            missing_project = await client.post(
                f"/api/v1/projects/{uuid4()}/tasks", json={"title": "Missing project"}
            )
            assert missing_project.status_code == 404

            created = await client.post(
                f"/api/v1/projects/{project_id}/tasks", json={"title": "Persisted task"}
            )
            assert created.status_code == 201
            task_id = created.json()["id"]

            listed = await client.get(
                f"/api/v1/projects/{project_id}/tasks", params={"page": 1, "limit": 1}
            )
            assert [task["id"] for task in listed.json()] == [task_id]

        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            fetched = await client.get(f"/api/v1/tasks/{task_id}")
            assert fetched.status_code == 200
            assert fetched.json()["title"] == "Persisted task"

            updated = await client.patch(
                f"/api/v1/tasks/{task_id}", json={"status": "IN_PROGRESS"}
            )
            assert updated.status_code == 200
            assert updated.json()["status"] == "IN_PROGRESS"

            deleted = await client.delete(f"/api/v1/tasks/{task_id}")
            assert deleted.status_code == 204
            assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 404

        async with session_factory() as session:
            users = BaseRepository(session, UserModel)
            _, total = await users.list(page=1, limit=20)
            assert total >= 1
            stored_user = await users.get(user_id)
            assert stored_user is not None
            stored_user.full_name = "Updated User"
            await users.save(stored_user)
            await session.commit()

        async with session_factory() as session:
            users = BaseRepository(session, UserModel)
            updated_user = await users.get(user_id)
            assert updated_user is not None
            assert updated_user.full_name == "Updated User"
    finally:
        async with session_factory() as session:
            await session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
            await BaseRepository(session, UserModel).delete(user_id)
            await session.commit()
        await engine.dispose()
