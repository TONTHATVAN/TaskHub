from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import AuthServiceDep, SessionServiceDep
from app.api.exceptions import InvalidRefreshTokenException, UnauthorizedException
from app.api.v1.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairRead,
    UserRead,
)
from app.application.session_service import InvalidCredentialsError
from app.application.tokens import InvalidTokenError, TokenPair
from app.core.messages import (
    EMAIL_ALREADY_REGISTERED_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
)
from app.domain.user import User
from app.domain.user_repository import EmailAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, service: AuthServiceDep) -> User:
    try:
        return await service.register(
            payload.email, payload.full_name, payload.password
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail=EMAIL_ALREADY_REGISTERED_MESSAGE
        ) from exc


@router.post("/login", response_model=TokenPairRead)
async def login(payload: LoginRequest, service: SessionServiceDep) -> TokenPair:
    try:
        return await service.login(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise UnauthorizedException(INVALID_CREDENTIALS_MESSAGE) from exc


@router.post("/refresh", response_model=TokenPairRead)
async def refresh(payload: RefreshRequest, service: SessionServiceDep) -> TokenPair:
    try:
        return await service.refresh(payload.refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenException() from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, service: SessionServiceDep) -> Response:
    try:
        await service.logout(payload.refresh_token)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenException() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
