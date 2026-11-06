from fastapi import HTTPException, status

from app.core.messages import (
    INVALID_ACCESS_TOKEN_MESSAGE,
    INVALID_REFRESH_TOKEN_MESSAGE,
)


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = INVALID_ACCESS_TOKEN_MESSAGE) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidRefreshTokenException(UnauthorizedException):
    def __init__(self) -> None:
        super().__init__(INVALID_REFRESH_TOKEN_MESSAGE)
