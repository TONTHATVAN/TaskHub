from http import HTTPStatus

from app.core.exceptions import AppException
from app.core.messages import (
    ACCESS_DENIED_MESSAGE,
    INACTIVE_WORKSPACE_MEMBER_MESSAGE,
    INVALID_TASK_ASSIGNEE_MESSAGE,
    LABEL_ALREADY_EXISTS_MESSAGE,
    LABEL_NOT_FOUND_MESSAGE,
    PROJECT_ARCHIVED_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    WORKSPACE_MEMBER_EXISTS_MESSAGE,
    WORKSPACE_MEMBER_NOT_FOUND_MESSAGE,
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


class ProjectArchivedError(AppException):
    def __init__(self) -> None:
        super().__init__(PROJECT_ARCHIVED_MESSAGE, HTTPStatus.CONFLICT)


class TaskNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(TASK_NOT_FOUND_MESSAGE)


class InvalidTaskAssigneeError(AppException):
    def __init__(self) -> None:
        super().__init__(INVALID_TASK_ASSIGNEE_MESSAGE, HTTPStatus.CONFLICT)


class UserNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(USER_NOT_FOUND_MESSAGE)


class WorkspaceNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(WORKSPACE_NOT_FOUND_MESSAGE)


class WorkspaceMemberNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(WORKSPACE_MEMBER_NOT_FOUND_MESSAGE)


class WorkspaceMemberExistsError(AppException):
    def __init__(self) -> None:
        super().__init__(WORKSPACE_MEMBER_EXISTS_MESSAGE, HTTPStatus.CONFLICT)


class InactiveWorkspaceMemberError(AppException):
    def __init__(self) -> None:
        super().__init__(INACTIVE_WORKSPACE_MEMBER_MESSAGE, HTTPStatus.CONFLICT)


class LabelNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(LABEL_NOT_FOUND_MESSAGE)


class LabelAlreadyExistsError(AppException):
    def __init__(self) -> None:
        super().__init__(LABEL_ALREADY_EXISTS_MESSAGE, HTTPStatus.CONFLICT)
