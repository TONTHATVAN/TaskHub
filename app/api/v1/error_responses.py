from typing import Any

from fastapi import status

from app.api.v1.error_schemas import ErrorRead
from app.core.constants import WWW_AUTHENTICATE_HEADER
from app.core.messages import (
    ACCESS_DENIED_MESSAGE,
    CURRENT_PASSWORD_INCORRECT_MESSAGE,
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    INACTIVE_USER_MESSAGE,
    INVALID_ACCESS_TOKEN_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
    INVALID_REFRESH_TOKEN_MESSAGE,
    INVALID_TASK_ASSIGNEE_MESSAGE,
    PROJECT_ARCHIVED_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)


def error_response(description: str) -> dict[str, Any]:
    return {"model": ErrorRead, "description": description}


def bearer_error_response(description: str) -> dict[str, Any]:
    return {
        "model": ErrorRead,
        "description": description,
        "headers": {WWW_AUTHENTICATE_HEADER: {"schema": {"type": "string"}}},
    }


ACCESS_DENIED_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: error_response(ACCESS_DENIED_MESSAGE)
}
UNAUTHORIZED_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: bearer_error_response(
        f"{INVALID_ACCESS_TOKEN_MESSAGE}; {INACTIVE_USER_MESSAGE}"
    )
}
LOGIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: bearer_error_response(
        f"{INVALID_CREDENTIALS_MESSAGE}; {INACTIVE_USER_MESSAGE}"
    )
}
REFRESH_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: bearer_error_response(
        f"{INVALID_REFRESH_TOKEN_MESSAGE}; {INACTIVE_USER_MESSAGE}"
    )
}
LOGOUT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: bearer_error_response(INVALID_REFRESH_TOKEN_MESSAGE)
}
EMAIL_CONFLICT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: error_response(EMAIL_ALREADY_REGISTERED_MESSAGE)
}
INCORRECT_PASSWORD_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: error_response(CURRENT_PASSWORD_INCORRECT_MESSAGE)
}

PROJECT_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: error_response(PROJECT_NOT_FOUND_MESSAGE)
}
TASK_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: error_response(TASK_NOT_FOUND_MESSAGE)
}
WORKSPACE_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: error_response(WORKSPACE_NOT_FOUND_MESSAGE)
}
ARCHIVED_PROJECT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: error_response(PROJECT_ARCHIVED_MESSAGE)
}
TASK_WRITE_CONFLICT_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: error_response(
        f"{PROJECT_ARCHIVED_MESSAGE}; {INVALID_TASK_ASSIGNEE_MESSAGE}"
    )
}

PROJECT_RESPONSES = (
    PROJECT_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)
TASK_RESPONSES = (
    TASK_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)
WORKSPACE_RESPONSES = (
    WORKSPACE_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)
