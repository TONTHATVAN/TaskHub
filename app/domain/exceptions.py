class NotFoundError(Exception):
    """A requested domain resource does not exist."""


class ProjectNotFoundError(NotFoundError):
    pass


class TaskNotFoundError(NotFoundError):
    pass
