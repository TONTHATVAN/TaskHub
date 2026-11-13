from fastapi import APIRouter, Response, status

from app.api.dependencies import AuthServiceDep, SessionServiceDep
from app.api.error_handling import app_error_response
from app.api.exceptions import (
    EmailAlreadyRegisteredException,
    InactiveUserException,
    InvalidRefreshTokenException,
    UnauthorizedException,
)
from app.api.v1.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairRead,
    UserRead,
)
from app.api.v1.error_responses import (
    EMAIL_CONFLICT_RESPONSES,
    LOGIN_RESPONSES,
    LOGOUT_RESPONSES,
    REFRESH_RESPONSES,
)
from app.application.session_service import (
    InactiveUserError,
    InvalidCredentialsError,
    ReplayedRefreshTokenError,
)
from app.application.tokens import InvalidTokenError, TokenPair
from app.core.messages import (
    INVALID_CREDENTIALS_MESSAGE,
)
from app.domain.user import User
from app.domain.user_repository import EmailAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=EMAIL_CONFLICT_RESPONSES,
)
async def register(payload: RegisterRequest, service: AuthServiceDep) -> User:
    try:
        return await service.register(
            payload.email, payload.full_name, payload.password
        )
    except EmailAlreadyExistsError as exc:
        raise EmailAlreadyRegisteredException() from exc


@router.post("/login", response_model=TokenPairRead, responses=LOGIN_RESPONSES)
async def login(payload: LoginRequest, service: SessionServiceDep) -> TokenPair:
    try:
        return await service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise UnauthorizedException(INVALID_CREDENTIALS_MESSAGE) from exc
    except InactiveUserError as exc:
        raise InactiveUserException() from exc


@router.post("/refresh", response_model=TokenPairRead, responses=REFRESH_RESPONSES)
async def refresh(
    payload: RefreshRequest, service: SessionServiceDep
) -> TokenPair | Response:
    try:
        return await service.refresh(payload.refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenException() from exc
    except ReplayedRefreshTokenError:
        # Return a response so the session dependency commits session revocation.
        return app_error_response(InvalidRefreshTokenException())
    except InactiveUserError as exc:
        raise InactiveUserException() from exc


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, responses=LOGOUT_RESPONSES
)
async def logout(payload: RefreshRequest, service: SessionServiceDep) -> Response:
    try:
        await service.logout(payload.refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenException() from exc
    except ReplayedRefreshTokenError:
        return app_error_response(InvalidRefreshTokenException())
    return Response(status_code=status.HTTP_204_NO_CONTENT)
