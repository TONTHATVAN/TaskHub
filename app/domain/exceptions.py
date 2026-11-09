from http import HTTPStatus

from app.core.exceptions import AppException
from app.core.messages import (
    ACCESS_DENIED_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)


class AccessDeniedError(AppException):
    def __init__(self) -> None:
        super().__init__(ACCESS_DENIED_MESSAGE, HTTPStatus.FORBIDDEN)


class NotFoundError(AppException):
    """A requested domain resource does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, HTTPStatus.NOT_FOUND)


class ProjectNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(PROJECT_NOT_FOUND_MESSAGE)


class TaskNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(TASK_NOT_FOUND_MESSAGE)


class UserNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(USER_NOT_FOUND_MESSAGE)


class WorkspaceNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(WORKSPACE_NOT_FOUND_MESSAGE)
