from http import HTTPStatus

from app.core.constants import BEARER_SCHEME, WWW_AUTHENTICATE_HEADER
from app.core.exceptions import AppException
from app.core.messages import (
    CURRENT_PASSWORD_INCORRECT_MESSAGE,
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    INACTIVE_USER_MESSAGE,
    INVALID_ACCESS_TOKEN_MESSAGE,
    INVALID_REFRESH_TOKEN_MESSAGE,
)


class EmailAlreadyRegisteredException(AppException):
    def __init__(self) -> None:
        super().__init__(
            EMAIL_ALREADY_REGISTERED_MESSAGE,
            HTTPStatus.CONFLICT,
        )


class IncorrectCurrentPasswordException(AppException):
    def __init__(self) -> None:
        super().__init__(
            CURRENT_PASSWORD_INCORRECT_MESSAGE,
            HTTPStatus.BAD_REQUEST,
        )


class UnauthorizedException(AppException):
    def __init__(self, detail: str = INVALID_ACCESS_TOKEN_MESSAGE) -> None:
        super().__init__(
            detail,
            HTTPStatus.UNAUTHORIZED,
            {WWW_AUTHENTICATE_HEADER: BEARER_SCHEME},
        )


class InvalidRefreshTokenException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__(INVALID_REFRESH_TOKEN_MESSAGE)


class InactiveUserException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__(INACTIVE_USER_MESSAGE)
