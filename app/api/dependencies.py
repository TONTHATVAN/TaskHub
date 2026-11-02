from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.task_service import TaskService
from app.domain.task_repository import TaskRepository
from app.infrastructure.database import get_session
from app.infrastructure.repositories.task import SqlTaskRepository


async def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_session, scope="function")],
) -> TaskRepository:
    return SqlTaskRepository(session)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
