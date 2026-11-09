from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import InactiveUserException, UnauthorizedException
from app.application.auth_service import AuthService
from app.application.profile_service import ProfileService
from app.application.session_service import SessionService
from app.application.task_authorization import TaskAuthorizationService
from app.application.task_service import TaskService
from app.application.tokens import InvalidTokenError, JwtTokenService, TokenType
from app.application.workspace_service import WorkspaceService
from app.domain.authorization import ProjectAccessRepository
from app.domain.refresh_token_repository import RefreshTokenRepository
from app.domain.task_repository import TaskRepository
from app.domain.user import User
from app.domain.user_repository import UserRepository
from app.domain.workspace_repository import WorkspaceRepository
from app.infrastructure.database import get_session
from app.infrastructure.repositories.authorization import SqlProjectAccessRepository
from app.infrastructure.repositories.refresh_token import SqlRefreshTokenRepository
from app.infrastructure.repositories.task import SqlTaskRepository
from app.infrastructure.repositories.user import SqlUserRepository
from app.infrastructure.repositories.workspace import SqlWorkspaceRepository
from app.infrastructure.settings import settings


async def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> TaskRepository:
    return SqlTaskRepository(session)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


async def get_project_access_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> ProjectAccessRepository:
    return SqlProjectAccessRepository(session)


def get_task_authorization_service(
    access: Annotated[ProjectAccessRepository, Depends(get_project_access_repository)],
    tasks: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskAuthorizationService:
    return TaskAuthorizationService(access, tasks)


TaskAuthorizationDep = Annotated[
    TaskAuthorizationService, Depends(get_task_authorization_service)
]


async def get_workspace_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> WorkspaceRepository:
    return SqlWorkspaceRepository(session)


def get_workspace_service(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    return WorkspaceService(repository)


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> UserRepository:
    return SqlUserRepository(session)


def get_auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_refresh_token_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> RefreshTokenRepository:
    return SqlRefreshTokenRepository(session)


def get_profile_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_tokens: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
) -> ProfileService:
    return ProfileService(users, refresh_tokens)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


def get_token_service() -> JwtTokenService:
    return JwtTokenService(
        secret_key=settings.jwt_secret_key.get_secret_value(),
        access_minutes=settings.jwt_access_minutes,
        refresh_days=settings.jwt_refresh_days,
    )


def get_session_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_tokens: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    tokens: Annotated[JwtTokenService, Depends(get_token_service)],
) -> SessionService:
    return SessionService(users, refresh_tokens, tokens)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    tokens: Annotated[JwtTokenService, Depends(get_token_service)],
) -> User:
    if credentials is None:
        raise UnauthorizedException()
    try:
        claims = tokens.decode(credentials.credentials, TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise UnauthorizedException() from exc
    user = await users.get_by_id(claims.user_id)
    if user is None:
        raise UnauthorizedException()
    if not user.is_active:
        raise InactiveUserException()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
