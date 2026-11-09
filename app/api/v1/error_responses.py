from typing import Any

from fastapi import status

from app.api.v1.error_schemas import ErrorRead
from app.core.messages import ACCESS_DENIED_MESSAGE, INVALID_ACCESS_TOKEN_MESSAGE

ACCESS_DENIED_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorRead,
        "description": ACCESS_DENIED_MESSAGE,
    }
}
UNAUTHORIZED_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorRead,
        "description": INVALID_ACCESS_TOKEN_MESSAGE,
        "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}},
    }
}
