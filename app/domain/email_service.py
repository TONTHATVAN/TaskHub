from typing import Protocol
from uuid import UUID


class EmailService(Protocol):
    async def send_task_assignment_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        task_title: str,
        task_id: UUID,
    ) -> None: ...
