import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.application.tokens import JwtTokenService
from app.infrastructure.database import engine, session_factory
from app.infrastructure.models import UserModel, WorkspaceModel
from app.infrastructure.settings import settings
from app.main import create_app


@pytest.mark.skipif(
    os.getenv("TASKHUB_RUN_DB_TESTS") != "1",
    reason="Set TASKHUB_RUN_DB_TESTS=1 to run against PostgreSQL",
)
def test_comment_workflow_with_postgres() -> None:
    asyncio.run(_exercise_comment_workflow())


async def _exercise_comment_workflow() -> None:
    owner_id, editor_id, viewer_id, outsider_id = (uuid4() for _ in range(4))
    users = (owner_id, editor_id, viewer_id, outsider_id)
    workspace_id: UUID | None = None
    try:
        async with session_factory() as session:
            session.add_all(
                UserModel(
                    id=user_id,
                    email=f"comment-{user_id}@example.invalid",
                    full_name="Comment User",
                    hashed_password="disabled",
                )
                for user_id in users
            )
            await session.commit()
        tokens = JwtTokenService(
            settings.jwt_secret_key.get_secret_value(),
            settings.jwt_access_minutes,
            settings.jwt_refresh_days,
        )
        owner = {"Authorization": f"Bearer {tokens.issue_access(owner_id)}"}
        editor = {"Authorization": f"Bearer {tokens.issue_access(editor_id)}"}
        viewer = {"Authorization": f"Bearer {tokens.issue_access(viewer_id)}"}
        outsider = {"Authorization": f"Bearer {tokens.issue_access(outsider_id)}"}
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            workspace = await client.post(
                "/api/v1/workspaces", json={"name": "Comment Team"}, headers=owner
            )
            assert workspace.status_code == 201
            workspace_id = UUID(workspace.json()["id"])
            for user_id, role in ((editor_id, "EDITOR"), (viewer_id, "VIEWER")):
                assert (
                    await client.post(
                        f"/api/v1/workspaces/{workspace_id}/members",
                        json={"user_id": str(user_id), "role": role},
                        headers=owner,
                    )
                ).status_code == 201
            project = await client.post(
                f"/api/v1/workspaces/{workspace_id}/projects",
                json={"name": "Main"},
                headers=owner,
            )
            assert project.status_code == 201
            project_id = project.json()["id"]
            task = await client.post(
                f"/api/v1/projects/{project_id}/tasks",
                json={"title": "Discuss"},
                headers=owner,
            )
            assert task.status_code == 201
            comments = f"/api/v1/tasks/{task.json()['id']}/comments"

            assert (await client.get(comments)).status_code == 401
            assert (await client.get(comments, headers=outsider)).status_code == 404
            assert (
                await client.post(comments, json={"content": "No"}, headers=viewer)
            ).status_code == 403
            for content in ("   ", "x" * 5001):
                assert (
                    await client.post(
                        comments, json={"content": content}, headers=editor
                    )
                ).status_code == 422
            created = await client.post(
                comments, json={"content": "  Please review  "}, headers=editor
            )
            assert created.status_code == 201
            comment_id = created.json()["id"]
            assert created.json()["author_id"] == str(editor_id)
            assert created.json()["content"] == "Please review"
            page = await client.get(
                comments, params={"page": 1, "limit": 1}, headers=viewer
            )
            assert page.status_code == 200
            assert page.json()["total"] == 1
            assert page.json()["items"][0]["id"] == comment_id
            assert (
                await client.get(comments, params={"page": 0}, headers=owner)
            ).status_code == 422
            assert (
                await client.delete(f"{comments}/{comment_id}", headers=outsider)
            ).status_code == 404
            assert (
                await client.delete(f"{comments}/{comment_id}", headers=viewer)
            ).status_code == 403
            assert (
                await client.delete(f"{comments}/{comment_id}", headers=owner)
            ).status_code == 204
            assert (
                await client.delete(f"{comments}/{comment_id}", headers=owner)
            ).status_code == 404

            owner_comment = await client.post(
                comments, json={"content": "Owner note"}, headers=owner
            )
            assert owner_comment.status_code == 201
            assert (
                await client.delete(
                    f"{comments}/{owner_comment.json()['id']}", headers=editor
                )
            ).status_code == 403
            assert (
                await client.delete(
                    f"{comments}/{owner_comment.json()['id']}", headers=owner
                )
            ).status_code == 204
            author_comment = await client.post(
                comments, json={"content": "Own note"}, headers=editor
            )
            assert author_comment.status_code == 201
            assert (
                await client.delete(
                    f"{comments}/{author_comment.json()['id']}", headers=editor
                )
            ).status_code == 204

            assert (
                await client.post(
                    f"/api/v1/projects/{project_id}/archive", headers=owner
                )
            ).status_code == 200
            assert (
                await client.post(comments, json={"content": "Late"}, headers=owner)
            ).status_code == 409
            assert (await client.get(comments, headers=viewer)).status_code == 200
    finally:
        async with session_factory() as session:
            if workspace_id is not None:
                await session.execute(
                    delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
                )
            await session.execute(delete(UserModel).where(UserModel.id.in_(users)))
            await session.commit()
        await engine.dispose()
