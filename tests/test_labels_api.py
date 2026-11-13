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
def test_label_workflow_with_postgres() -> None:
    asyncio.run(_exercise_label_workflow())


async def _exercise_label_workflow() -> None:
    owner_id, viewer_id, outsider_id = uuid4(), uuid4(), uuid4()
    users = (owner_id, viewer_id, outsider_id)
    workspace_id: UUID | None = None
    try:
        async with session_factory() as session:
            session.add_all(
                UserModel(
                    id=user_id,
                    email=f"label-{user_id}@example.invalid",
                    full_name="Label User",
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
        viewer = {"Authorization": f"Bearer {tokens.issue_access(viewer_id)}"}
        outsider = {"Authorization": f"Bearer {tokens.issue_access(outsider_id)}"}
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            workspace = await client.post(
                "/api/v1/workspaces", json={"name": "Label Team"}, headers=owner
            )
            assert workspace.status_code == 201
            workspace_id = UUID(workspace.json()["id"])
            assert (
                await client.post(
                    f"/api/v1/workspaces/{workspace_id}/members",
                    json={"user_id": str(viewer_id), "role": "VIEWER"},
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
            labels = f"/api/v1/projects/{project_id}/labels"
            task = await client.post(
                f"/api/v1/projects/{project_id}/tasks",
                json={"title": "Review"},
                headers=owner,
            )
            assert task.status_code == 201
            task_labels = f"/api/v1/tasks/{task.json()['id']}/labels"

            assert (await client.get(labels, headers=outsider)).status_code == 404
            assert (
                await client.post(
                    labels, json={"name": "X", "color": "#123456"}, headers=viewer
                )
            ).status_code == 403
            for payload in (
                {"name": "   ", "color": "#123456"},
                {"name": "x" * 101, "color": "#123456"},
                {"name": "Good", "color": "red"},
            ):
                assert (
                    await client.post(labels, json=payload, headers=owner)
                ).status_code == 422
            created = await client.post(
                labels, json={"name": "  Urgent  ", "color": "#A1b2C3"}, headers=owner
            )
            assert created.status_code == 201
            label_id = created.json()["id"]
            assert created.json()["name"] == "Urgent"
            assert (
                await client.post(
                    labels, json={"name": "Urgent", "color": "#000000"}, headers=owner
                )
            ).status_code == 409
            assert (
                await client.patch(
                    f"{labels}/{label_id}", json={"name": None}, headers=owner
                )
            ).status_code == 422
            updated = await client.patch(
                f"{labels}/{label_id}", json={"color": "#FFFFFF"}, headers=owner
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Urgent"
            page = await client.get(
                labels, params={"page": 1, "limit": 1}, headers=viewer
            )
            assert page.status_code == 200
            assert page.json()["total"] == 1
            assert page.json()["items"][0]["id"] == label_id
            assert (
                await client.get(labels, params={"page": 0}, headers=owner)
            ).status_code == 422

            second = await client.post(
                labels, json={"name": "Later", "color": "#123456"}, headers=owner
            )
            assert second.status_code == 201
            assert (
                await client.patch(
                    f"{labels}/{second.json()['id']}",
                    json={"name": "Urgent"},
                    headers=owner,
                )
            ).status_code == 409
            assert (
                await client.get(f"{labels}/{second.json()['id']}", headers=owner)
            ).json()["name"] == "Later"
            assert (
                await client.delete(f"{labels}/{second.json()['id']}", headers=owner)
            ).status_code == 204

            assert (
                await client.post(f"{task_labels}/{label_id}", headers=viewer)
            ).status_code == 403
            assert (
                await client.post(f"{task_labels}/{label_id}", headers=owner)
            ).status_code == 204
            assert (
                await client.post(f"{task_labels}/{label_id}", headers=owner)
            ).status_code == 204
            assert [
                item["id"]
                for item in (await client.get(task_labels, headers=viewer)).json()
            ] == [label_id]
            other_project = await client.post(
                f"/api/v1/workspaces/{workspace_id}/projects",
                json={"name": "Other"},
                headers=owner,
            )
            assert other_project.status_code == 201
            other_label = await client.post(
                f"/api/v1/projects/{other_project.json()['id']}/labels",
                json={"name": "Other", "color": "#000000"},
                headers=owner,
            )
            assert other_label.status_code == 201
            assert (
                await client.post(
                    f"{task_labels}/{other_label.json()['id']}", headers=owner
                )
            ).status_code == 404
            assert (
                await client.delete(f"{task_labels}/{label_id}", headers=owner)
            ).status_code == 204
            assert (await client.get(task_labels, headers=owner)).json() == []
            assert (
                await client.delete(f"{labels}/{label_id}", headers=owner)
            ).status_code == 204
            assert (
                await client.get(f"{labels}/{label_id}", headers=owner)
            ).status_code == 404

            assert (
                await client.post(
                    f"/api/v1/projects/{project_id}/archive", headers=owner
                )
            ).status_code == 200
            assert (
                await client.post(
                    labels, json={"name": "Late", "color": "#000000"}, headers=owner
                )
            ).status_code == 409
            assert (await client.get(labels, headers=viewer)).status_code == 200
    finally:
        async with session_factory() as session:
            if workspace_id is not None:
                await session.execute(
                    delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
                )
            await session.execute(delete(UserModel).where(UserModel.id.in_(users)))
            await session.commit()
        await engine.dispose()
