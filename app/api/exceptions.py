from fastapi import HTTPException, status

from app.core.constants import BEARER_SCHEME
from app.core.messages import (
    CURRENT_PASSWORD_INCORRECT_MESSAGE,
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    INVALID_ACCESS_TOKEN_MESSAGE,
    INVALID_REFRESH_TOKEN_MESSAGE,
)


class EmailAlreadyRegisteredException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=EMAIL_ALREADY_REGISTERED_MESSAGE,
        )


class IncorrectCurrentPasswordException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=CURRENT_PASSWORD_INCORRECT_MESSAGE,
        )


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = INVALID_ACCESS_TOKEN_MESSAGE) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": BEARER_SCHEME},
        )


class InvalidRefreshTokenException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__(INVALID_REFRESH_TOKEN_MESSAGE)
