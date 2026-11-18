import logging
from dataclasses import dataclass
from email.message import EmailMessage
from uuid import UUID

import aiosmtplib
from aiosmtplib.errors import SMTPException

logger = logging.getLogger(__name__)


class SmtpEmailService:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1025,
        username: str | None = None,
        password: str | None = None,
        sender: str = "noreply@taskhub.com",
        use_tls: bool = False,
        enabled: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.use_tls = use_tls
        self.enabled = enabled

    async def send_task_assignment_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        if not self.enabled:
            return

        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient_email
        message["Subject"] = f"[TaskHub] You were assigned to task: {task_title}"
        message.set_content(
            f"Hello {recipient_name},\n\n"
            f'You have been assigned to task "{task_title}" (ID: {task_id}).\n\n'
            "Please check TaskHub for more details.\n\n"
            "Best regards,\nTaskHub Team"
        )
        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
        except (SMTPException, OSError, TimeoutError) as exc:
            logger.warning(
                "Failed to send assignment email to %s: %s", recipient_email, exc
            )


@dataclass(frozen=True, slots=True)
class SentAssignmentEmail:
    recipient_email: str
    recipient_name: str
    task_title: str
    task_id: UUID


class InMemoryEmailService:
    def __init__(self) -> None:
        self.sent_emails: list[SentAssignmentEmail] = []

    async def send_task_assignment_email(
        self,
        *,
        recipient_email: str,
        recipient_name: str,
        task_title: str,
        task_id: UUID,
    ) -> None:
        self.sent_emails.append(
            SentAssignmentEmail(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                task_title=task_title,
                task_id=task_id,
            )
        )
