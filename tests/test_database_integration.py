import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.dependencies import get_current_user
from app.application.tokens import JwtTokenService
from app.domain.exceptions import NotFoundError, TaskNotFoundError, UserNotFoundError
from app.domain.task import TaskPriority, TaskStatus
from app.domain.user import User, UserRole
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
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.settings import settings
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


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_stale_base_save() -> None:
    asyncio.run(_exercise_stale_base_save())


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_profile_update_preserves_other_fields() -> None:
    asyncio.run(_exercise_profile_update())


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_postgres_task_permissions() -> None:
    asyncio.run(_exercise_task_permissions())


async def _exercise_task_permissions() -> None:
    project_id = uuid4()
    workspace_id = uuid4()
    role_names = ("owner", "editor", "viewer", "outsider", "admin")
    users = {
        name: UserModel(
            id=uuid4(),
            email=f"{name}-{uuid4()}@example.invalid",
            full_name=name,
            hashed_password="disabled",
            role=UserRole.ADMIN if name == "admin" else UserRole.MEMBER,
        )
        for name in role_names
    }
    try:
        async with session_factory() as session:
            workspace = WorkspaceModel(
                id=workspace_id, name="Permissions", owner=users["owner"]
            )
            workspace.members.extend(
                (
                    WorkspaceMemberModel(
                        user=users["editor"], role=WorkspaceRole.EDITOR
                    ),
                    WorkspaceMemberModel(
                        user=users["viewer"], role=WorkspaceRole.VIEWER
                    ),
                )
            )
            session.add_all(users.values())
            session.add(
                ProjectModel(id=project_id, name="Permissions", workspace=workspace)
            )
            await session.commit()

        tokens = JwtTokenService(
            settings.jwt_secret_key.get_secret_value(),
            settings.jwt_access_minutes,
            settings.jwt_refresh_days,
        )

        def headers(name: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {tokens.issue_access(users[name].id)}"}

        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            endpoint = f"/api/v1/projects/{project_id}/tasks"
            assert (await client.get(endpoint)).status_code == 401
            created = await client.post(
                endpoint, json={"title": "Protected"}, headers=headers("owner")
            )
            assert created.status_code == 201
            task_endpoint = f"/api/v1/tasks/{created.json()['id']}"

            assert (
                await client.get(endpoint, headers=headers("viewer"))
            ).status_code == 200
            assert (
                await client.get(task_endpoint, headers=headers("viewer"))
            ).status_code == 200
            for response in (
                await client.post(
                    endpoint, json={"title": "Denied"}, headers=headers("viewer")
                ),
                await client.patch(
                    task_endpoint,
                    json={"title": "Denied"},
                    headers=headers("viewer"),
                ),
                await client.delete(task_endpoint, headers=headers("viewer")),
                await client.get(endpoint, headers=headers("outsider")),
                await client.get(task_endpoint, headers=headers("outsider")),
            ):
                assert response.status_code == 403
            assert (await client.get(task_endpoint, headers=headers("owner"))).json()[
                "title"
            ] == "Protected"

            assert (
                await client.patch(
                    task_endpoint,
                    json={"title": "Edited"},
                    headers=headers("editor"),
                )
            ).status_code == 200
            assert (
                await client.post(
                    endpoint, json={"title": "Second"}, headers=headers("editor")
                )
            ).status_code == 201
            async with session_factory() as session:
                await session.execute(
                    delete(WorkspaceMemberModel).where(
                        WorkspaceMemberModel.workspace_id == workspace_id,
                        WorkspaceMemberModel.user_id == users["editor"].id,
                    )
                )
                await session.commit()
            assert (
                await client.patch(
                    task_endpoint,
                    json={"title": "After removal"},
                    headers=headers("editor"),
                )
            ).status_code == 403
            assert (
                await client.delete(task_endpoint, headers=headers("admin"))
            ).status_code == 204
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
            )
            await session.execute(
                delete(UserModel).where(
                    UserModel.id.in_([user.id for user in users.values()])
                )
            )
            await session.commit()
        await engine.dispose()


async def _exercise_profile_update() -> None:
    user_id = uuid4()
    async with session_factory() as session:
        await BaseRepository(session, UserModel).add(
            UserModel(
                id=user_id,
                email=f"profile-{user_id}@example.invalid",
                full_name="Original",
                hashed_password="disabled",
            )
        )
        await session.commit()

    try:
        async with session_factory() as stale_session:
            users = SqlUserRepository(stale_session)
            old = await users.get_by_id(user_id)
            assert old is not None
            async with session_factory() as other_session:
                other_users = SqlUserRepository(other_session)
                await other_users.update_profile(user_id, {"full_name": "New Name"})
                await other_session.commit()

            updated = await users.update_profile(
                user_id, {"email": f"new-{user_id}@example.invalid"}
            )
            assert updated.full_name == "New Name"
            await stale_session.commit()

        async with session_factory() as session:
            stored = await SqlUserRepository(session).get_by_id(user_id)
            assert stored is not None
            assert stored.full_name == "New Name"
            assert stored.email == f"new-{user_id}@example.invalid"
            await BaseRepository(session, UserModel).delete(user_id)
            await session.commit()

        async with session_factory() as session:
            users = SqlUserRepository(session)
            with pytest.raises(UserNotFoundError):
                await users.update_profile(user_id, {"full_name": "Missing"})
            with pytest.raises(UserNotFoundError):
                await users.update_password(user_id, "unused")
    finally:
        async with session_factory() as session:
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
        await engine.dispose()


async def _exercise_stale_base_save() -> None:
    user_id = uuid4()
    async with session_factory() as session:
        await BaseRepository(session, UserModel).add(
            UserModel(
                id=user_id,
                email=f"stale-{user_id}@example.invalid",
                full_name="Original",
                hashed_password="disabled",
            )
        )
        await session.commit()

    try:
        async with session_factory() as stale_session:
            users = BaseRepository(stale_session, UserModel)
            stale_user = await users.get(user_id)
            assert stale_user is not None
            stale_user.full_name = "Stale update"
            async with session_factory() as deleting_session:
                assert await BaseRepository(deleting_session, UserModel).delete(user_id)
                await deleting_session.commit()
            with pytest.raises(NotFoundError):
                await users.save(stale_user)
            await stale_session.rollback()
    finally:
        async with session_factory() as session:
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
        await engine.dispose()


async def _exercise_auth() -> None:
    email = f"auth-{uuid4()}@example.com"
    updated_email = f"updated-{uuid4()}@example.com"
    other_email = f"other-{uuid4()}@example.com"
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

            headers = {"Authorization": f"Bearer {pair['access_token']}"}
            assert (
                await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": other_email,
                        "full_name": "Other User",
                        "password": "secret-pass-123",
                    },
                )
            ).status_code == 201
            assert (
                await client.patch(
                    "/api/v1/users/me",
                    json={"email": other_email},
                    headers=headers,
                )
            ).status_code == 409
            assert (await client.get("/api/v1/users/me", headers=headers)).json()[
                "email"
            ] == email
            updated = await client.patch(
                "/api/v1/users/me",
                json={"email": updated_email.upper(), "full_name": "Updated Profile"},
                headers=headers,
            )
            assert updated.status_code == 200
            assert updated.json()["email"] == updated_email
            assert updated.json()["full_name"] == "Updated Profile"
            assert (
                await client.post(
                    "/api/v1/users/me/change-password",
                    json={
                        "current_password": "wrong-password",
                        "new_password": "new-secret-pass-123",
                    },
                    headers=headers,
                )
            ).status_code == 400
            changed = await client.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "secret-pass-123",
                    "new_password": "new-secret-pass-123",
                },
                headers=headers,
            )
            assert changed.status_code == 204
            assert (
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": updated_email, "password": "secret-pass-123"},
                )
            ).status_code == 401
            assert (
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": updated_email, "password": "new-secret-pass-123"},
                )
            ).status_code == 200

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
            assert len(stored_tokens) == 3
            assert sum(token.revoked_at is not None for token in stored_tokens) == 2
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(UserModel).where(
                    UserModel.email.in_((email, updated_email, other_email))
                )
            )
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

        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: User(
            id=user_id,
            email=user.email,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            role=UserRole.MEMBER,
            is_active=True,
            created_at=user.created_at,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
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
            next_page = await client.get(
                f"/api/v1/projects/{project_id}/tasks", params={"page": 2, "limit": 1}
            )
            page_ids = [task["id"] for task in listed.json() + next_page.json()]
            assert len(page_ids) == 2
            assert set(page_ids) == {task_id, second.json()["id"]}

        async with session_factory() as session:
            stale_task = await SqlTaskRepository(session).get(UUID(task_id))
            assert stale_task is not None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
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

            async with session_factory() as session:
                await SqlTaskRepository(session).save(
                    stale_task, {"priority": TaskPriority.HIGH}
                )
                await session.commit()
            fetched_after_stale_save = await client.get(f"/api/v1/tasks/{task_id}")
            assert fetched_after_stale_save.json()["status"] == TaskStatus.IN_PROGRESS
            assert fetched_after_stale_save.json()["priority"] == TaskPriority.HIGH

            deleted = await client.delete(f"/api/v1/tasks/{task_id}")
            assert deleted.status_code == 204
            assert (await client.get(f"/api/v1/tasks/{task_id}")).status_code == 404

        async with session_factory() as session:
            tasks = SqlTaskRepository(session)
            with pytest.raises(TaskNotFoundError):
                await tasks.save(stale_task, {"priority": TaskPriority.LOW})
            assert await tasks.delete(UUID(task_id)) is False

        async with session_factory() as session:
            users = BaseRepository(session, UserModel)
            _, total = await users.list(page=1, limit=20)
            assert total >= 1
            stored_user = await users.get(user_id)
            assert stored_user is not None
            stored_user.full_name = "Updated User"
            await users.save(stored_user)
            with pytest.raises(NotFoundError):
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
            with pytest.raises(NotFoundError):
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
