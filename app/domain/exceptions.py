from app.core.messages import (
    ACCESS_DENIED_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)


class AccessDeniedError(Exception):
    def __init__(self) -> None:
        self.message = ACCESS_DENIED_MESSAGE
        super().__init__(self.message)


class NotFoundError(Exception):
    """A requested domain resource does not exist."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


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
