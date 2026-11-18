from uuid import UUID

from fastapi import BackgroundTasks

from app.domain.email_service import EmailService
from app.domain.user_repository import UserRepository


class TaskNotificationService:
    def __init__(self, users: UserRepository, email_service: EmailService) -> None:
        self._users = users
        self._email = email_service

    async def notify_assignee_in_background(
        self,
        background_tasks: BackgroundTasks,
        *,
        assignee_id: UUID,
        task_title: str,
        task_id: UUID,
    ) -> None:
        assignee = await self._users.get_by_id(assignee_id)
        if assignee is not None and assignee.is_active:
            background_tasks.add_task(
                self._email.send_task_assignment_email,
                recipient_email=assignee.email,
                recipient_name=assignee.full_name,
                task_title=task_title,
                task_id=task_id,
            )
