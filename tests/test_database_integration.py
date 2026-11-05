import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.domain.exceptions import TaskNotFoundError
from app.infrastructure.database import engine, session_factory
from app.infrastructure.models import (
    ProjectModel,
    RefreshTokenModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
    WorkspaceRole,
)
from app.infrastructure.repositories.base import BaseRepository
from app.infrastructure.repositories.task import SqlTaskRepository
from app.main import create_app


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_task_crud_and_persistence() -> None:
    asyncio.run(_exercise_database())


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_auth_token_rotation() -> None:
    asyncio.run(_exercise_auth())


async def _exercise_auth() -> None:
    email = f"auth-{uuid4()}@example.com"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "full_name": "Auth Test",
                    "password": "secret-pass-123",
                },
            )
            assert registered.status_code == 201
            user_id = UUID(registered.json()["id"])
            assert (
                await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "full_name": "Auth Test",
                        "password": "secret-pass-123",
                    },
                )
            ).status_code == 409
            assert (
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "wrong-pass"},
                )
            ).status_code == 401

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "secret-pass-123"},
            )
            assert login.status_code == 200
            pair = login.json()

        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            me = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {pair['access_token']}"},
            )
            assert me.status_code == 200
            assert me.json()["email"] == email

            refreshed = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            )
            assert refreshed.status_code == 200
            assert (
                await client.post(
                    "/api/v1/auth/refresh",
                    json={"refresh_token": pair["refresh_token"]},
                )
            ).status_code == 401

            new_refresh_token = refreshed.json()["refresh_token"]
            assert (
                await client.post(
                    "/api/v1/auth/logout", json={"refresh_token": new_refresh_token}
                )
            ).status_code == 204
            assert (
                await client.post(
                    "/api/v1/auth/refresh", json={"refresh_token": new_refresh_token}
                )
            ).status_code == 401

        async with session_factory() as session:
            tokens = await session.scalars(
                select(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id)
            )
            stored_tokens = list(tokens)
            assert len(stored_tokens) == 2
            assert all(token.revoked_at is not None for token in stored_tokens)
    finally:
        async with session_factory() as session:
            await session.execute(delete(UserModel).where(UserModel.email == email))
            await session.commit()
        await engine.dispose()


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
            workspace.members.append(
                WorkspaceMemberModel(user=user, role=WorkspaceRole.OWNER)
            )
            project = ProjectModel(
                id=project_id, name="Integration", workspace=workspace
            )
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

            second = await client.post(
                f"/api/v1/projects/{project_id}/tasks", json={"title": "Second task"}
            )
            assert second.status_code == 201

            listed = await client.get(
                f"/api/v1/projects/{project_id}/tasks", params={"page": 1, "limit": 1}
            )
            assert [task["id"] for task in listed.json()] == [task_id]
            next_page = await client.get(
                f"/api/v1/projects/{project_id}/tasks", params={"page": 2, "limit": 1}
            )
            assert [task["id"] for task in next_page.json()] == [second.json()["id"]]

        async with session_factory() as session:
            stale_task = await SqlTaskRepository(session).get(UUID(task_id))
            assert stale_task is not None

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

            rejected = await client.patch(
                f"/api/v1/tasks/{task_id}", json={"title": None}
            )
            assert rejected.status_code == 422
            fetched_after_rejection = await client.get(f"/api/v1/tasks/{task_id}")
            assert fetched_after_rejection.status_code == 200
            assert fetched_after_rejection.json()["title"] == "Persisted task"

            deleted = await client.delete(f"/api/v1/tasks/{task_id}")
            assert deleted.status_code == 204
            assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 404

        async with session_factory() as session:
            tasks = SqlTaskRepository(session)
            with pytest.raises(TaskNotFoundError):
                await tasks.save(stale_task)
            assert await tasks.delete(UUID(task_id)) is False

        async with session_factory() as session:
            users = BaseRepository(session, UserModel)
            _, total = await users.list(page=1, limit=20)
            assert total >= 1
            stored_user = await users.get(user_id)
            assert stored_user is not None
            stored_user.full_name = "Updated User"
            await users.save(stored_user)
            with pytest.raises(LookupError):
                await users.save(
                    UserModel(
                        id=uuid4(),
                        email=f"missing-{uuid4()}@example.invalid",
                        full_name="Missing",
                        hashed_password="disabled",
                    )
                )

            memberships = BaseRepository(session, WorkspaceMemberModel)
            member = await memberships.get((workspace_id, user_id))
            assert member is not None
            member.role = WorkspaceRole.EDITOR
            await memberships.save(member)
            with pytest.raises(LookupError):
                await memberships.save(
                    WorkspaceMemberModel(
                        workspace_id=workspace_id,
                        user_id=uuid4(),
                        role=WorkspaceRole.VIEWER,
                    )
                )
            await session.commit()

        async with session_factory() as session:
            users = BaseRepository(session, UserModel)
            updated_user = await users.get(user_id)
            assert updated_user is not None
            assert updated_user.full_name == "Updated User"
            updated_member = await BaseRepository(session, WorkspaceMemberModel).get(
                (workspace_id, user_id)
            )
            assert updated_member is not None
            assert updated_member.role == WorkspaceRole.EDITOR
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
            )
            await BaseRepository(session, UserModel).delete(user_id)
            await session.commit()
        await engine.dispose()
