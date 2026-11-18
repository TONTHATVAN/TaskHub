from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_email_service,
    get_task_authorization_service,
    get_task_cache_service,
    get_task_repository,
    get_user_repository,
)
from app.application.notification_service import TaskNotificationService
from app.domain.authorization import ProjectAccess
from app.domain.project import Project, ProjectStatus
from app.domain.task import Task
from app.domain.user import User, UserRole
from app.domain.user_repository import UserProfileChanges
from app.infrastructure.email import InMemoryEmailService, SmtpEmailService
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository
from app.infrastructure.task_cache import InMemoryTaskCacheService
from app.main import create_app


class MemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    def add_user(
        self,
        user_id: UUID,
        email: str = "member@example.com",
        full_name: str = "Member User",
        is_active: bool = True,
    ) -> User:
        user = User(
            id=user_id,
            email=email,
            full_name=full_name,
            hashed_password="disabled",
            role=UserRole.MEMBER,
            is_active=is_active,
            created_at=datetime.now(UTC),
        )
        self.users[user_id] = user
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        return await self.get_by_id(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def get_by_email_for_update(self, email: str) -> User | None:
        return await self.get_by_email(email)

    async def add(self, email: str, full_name: str, hashed_password: str) -> User:
        return self.add_user(uuid4(), email=email, full_name=full_name)

    async def update_profile(self, user_id: UUID, changes: UserProfileChanges) -> User:
        return self.users[user_id]

    async def update_password(
        self, user_id: UUID, expected_hash: str, hashed_password: str
    ) -> bool:
        return True


@pytest.mark.asyncio
async def test_smtp_email_service_disabled() -> None:
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        service = SmtpEmailService(enabled=False)
        await service.send_task_assignment_email(
            recipient_email="test@example.com",
            recipient_name="Tester",
            task_title="Test Task",
            task_id=uuid4(),
        )
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_email_service_sends_email() -> None:
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        service = SmtpEmailService(
            host="mail.example.com",
            port=587,
            sender="admin@example.com",
            enabled=True,
        )
        task_id = uuid4()
        await service.send_task_assignment_email(
            recipient_email="assignee@example.com",
            recipient_name="Jane Doe",
            task_title="Important Task",
            task_id=task_id,
        )
        mock_send.assert_awaited_once()
        call_args = mock_send.call_args
        message = call_args[0][0]
        assert message["From"] == "admin@example.com"
        assert message["To"] == "assignee@example.com"
        assert "Important Task" in message["Subject"]
        assert "Important Task" in message.get_content()
        assert str(task_id) in message.get_content()


@pytest.mark.asyncio
async def test_smtp_email_service_graceful_fallback_on_error() -> None:
    with patch(
        "aiosmtplib.send", new_callable=AsyncMock, side_effect=OSError("SMTP down")
    ):
        service = SmtpEmailService(enabled=True)
        # Should not raise exception
        await service.send_task_assignment_email(
            recipient_email="test@example.com",
            recipient_name="Tester",
            task_title="Task",
            task_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_in_memory_email_service() -> None:
    service = InMemoryEmailService()
    task_id = uuid4()
    await service.send_task_assignment_email(
        recipient_email="user@example.com",
        recipient_name="User Name",
        task_title="Sample Task",
        task_id=task_id,
    )
    assert len(service.sent_emails) == 1
    sent = service.sent_emails[0]
    assert sent.recipient_email == "user@example.com"
    assert sent.recipient_name == "User Name"
    assert sent.task_title == "Sample Task"
    assert sent.task_id == task_id


@pytest.mark.asyncio
async def test_task_notification_service_logic() -> None:
    user_repo = MemoryUserRepository()
    email_service = InMemoryEmailService()
    notification_service = TaskNotificationService(user_repo, email_service)

    active_user_id = uuid4()
    user_repo.add_user(
        active_user_id, email="active@example.com", full_name="Active", is_active=True
    )

    inactive_user_id = uuid4()
    user_repo.add_user(
        inactive_user_id,
        email="inactive@example.com",
        full_name="Inactive",
        is_active=False,
    )

    bg_tasks = BackgroundTasks()

    # 1. Active user: task is scheduled
    await notification_service.notify_assignee_in_background(
        bg_tasks,
        assignee_id=active_user_id,
        task_title="Task 1",
        task_id=uuid4(),
    )
    assert len(bg_tasks.tasks) == 1

    # 2. Inactive user: not scheduled
    bg_tasks_2 = BackgroundTasks()
    await notification_service.notify_assignee_in_background(
        bg_tasks_2,
        assignee_id=inactive_user_id,
        task_title="Task 2",
        task_id=uuid4(),
    )
    assert len(bg_tasks_2.tasks) == 0

    # 3. Non-existent user: not scheduled
    bg_tasks_3 = BackgroundTasks()
    await notification_service.notify_assignee_in_background(
        bg_tasks_3,
        assignee_id=uuid4(),
        task_title="Task 3",
        task_id=uuid4(),
    )
    assert len(bg_tasks_3.tasks) == 0


def test_api_task_assignment_notification_flow() -> None:
    repository = InMemoryTaskRepository()
    cache = InMemoryTaskCacheService()
    email_service = InMemoryEmailService()
    user_repo = MemoryUserRepository()

    project_id = uuid4()
    assignee_1_id = uuid4()
    assignee_2_id = uuid4()

    repository.assignable_users.add(assignee_1_id)
    repository.assignable_users.add(assignee_2_id)

    user_repo.add_user(
        assignee_1_id,
        email="assignee1@example.com",
        full_name="Assignee One",
    )
    user_repo.add_user(
        assignee_2_id,
        email="assignee2@example.com",
        full_name="Assignee Two",
    )

    class AllowTestAccess:
        def __init__(self, repo: InMemoryTaskRepository) -> None:
            self.repo = repo

        async def require_project(
            self, user: User, proj_id: UUID, *, write: bool
        ) -> ProjectAccess:
            return ProjectAccess(
                owner_id=user.id,
                member_role=None,
                project=Project(
                    proj_id,
                    uuid4(),
                    "Notification Project",
                    None,
                    ProjectStatus.ACTIVE,
                    datetime.now(UTC),
                ),
            )

        async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
            task = await self.repo.get(task_id)
            assert task is not None
            return task

    app = create_app()
    app.dependency_overrides[get_task_repository] = lambda: repository
    app.dependency_overrides[get_task_cache_service] = lambda: cache
    app.dependency_overrides[get_email_service] = lambda: email_service
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid4(),
        email="creator@example.com",
        full_name="Creator",
        hashed_password="disabled",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_task_authorization_service] = lambda: AllowTestAccess(
        repository
    )

    with TestClient(app) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"

        # 1. Create task without assignee -> No email sent
        res_unassigned = client.post(endpoint, json={"title": "Unassigned Task"})
        assert res_unassigned.status_code == 201
        assert len(email_service.sent_emails) == 0

        # 2. Create task with assignee 1 -> Background task sends email to assignee 1
        res_assigned = client.post(
            endpoint,
            json={
                "title": "First Assigned Task",
                "assignee_id": str(assignee_1_id),
            },
        )
        assert res_assigned.status_code == 201
        task_id = res_assigned.json()["id"]
        assert len(email_service.sent_emails) == 1
        assert email_service.sent_emails[0].recipient_email == "assignee1@example.com"
        assert email_service.sent_emails[0].task_title == "First Assigned Task"

        # 3. Patch task without changing assignee -> No new email sent
        res_patch_title = client.patch(
            f"/api/v1/tasks/{task_id}", json={"title": "Updated Title"}
        )
        assert res_patch_title.status_code == 200
        assert len(email_service.sent_emails) == 1  # Still 1

        # 4. Patch task with same assignee -> No new email sent
        res_patch_same = client.patch(
            f"/api/v1/tasks/{task_id}", json={"assignee_id": str(assignee_1_id)}
        )
        assert res_patch_same.status_code == 200
        assert len(email_service.sent_emails) == 1  # Still 1

        # 5. Patch task with new assignee 2 -> Email sent to assignee 2
        res_patch_new = client.patch(
            f"/api/v1/tasks/{task_id}", json={"assignee_id": str(assignee_2_id)}
        )
        assert res_patch_new.status_code == 200
        assert len(email_service.sent_emails) == 2
        assert email_service.sent_emails[1].recipient_email == "assignee2@example.com"
        assert email_service.sent_emails[1].task_title == "Updated Title"

        # 6. Unassign task -> No new email sent
        res_unassign = client.patch(
            f"/api/v1/tasks/{task_id}", json={"assignee_id": None}
        )
        assert res_unassign.status_code == 200
        assert len(email_service.sent_emails) == 2  # Still 2
