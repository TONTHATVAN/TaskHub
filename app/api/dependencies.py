from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth_service import AuthService
from app.application.task_service import TaskService
from app.domain.task_repository import TaskRepository
from app.domain.user_repository import UserRepository
from app.infrastructure.database import get_session
from app.infrastructure.repositories.task import SqlTaskRepository
from app.infrastructure.repositories.user import SqlUserRepository


async def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> TaskRepository:
    return SqlTaskRepository(session)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> UserRepository:
    return SqlUserRepository(session)


def get_auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(repository)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
