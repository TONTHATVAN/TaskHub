from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUserDep, TaskAuthorizationDep, TaskServiceDep
from app.api.v1.task_schemas import ErrorRead, TaskCreate, TaskRead, TaskUpdate
from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import (
    ACCESS_DENIED_MESSAGE,
    INVALID_ACCESS_TOKEN_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
)
from app.domain.task import Task

projects_router = APIRouter(prefix="/projects", tags=["tasks"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])
TASK_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorRead,
        "description": TASK_NOT_FOUND_MESSAGE,
    }
}
PROJECT_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorRead,
        "description": PROJECT_NOT_FOUND_MESSAGE,
    }
}
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
PROJECT_RESPONSES = (
    PROJECT_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)
TASK_RESPONSES = (
    TASK_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)


@projects_router.post(
    "/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    responses=PROJECT_RESPONSES,
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    service: TaskServiceDep,
    authorization: TaskAuthorizationDep,
    user: CurrentUserDep,
) -> Task:
    await authorization.require_project(user, project_id, write=True)
    return await service.create(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
    )


@projects_router.get(
    "/{project_id}/tasks",
    response_model=list[TaskRead],
    responses=PROJECT_RESPONSES,
)
async def list_tasks(
    project_id: UUID,
    service: TaskServiceDep,
    authorization: TaskAuthorizationDep,
    user: CurrentUserDep,
    page: Annotated[int, Query(ge=PAGE_MIN)] = PAGE_DEFAULT,
    limit: Annotated[int, Query(ge=LIMIT_MIN, le=LIMIT_MAX)] = LIMIT_DEFAULT,
) -> list[Task]:
    await authorization.require_project(user, project_id, write=False)
    return await service.list_by_project(project_id, page=page, limit=limit)


@tasks_router.get(
    "/{task_id}",
    response_model=TaskRead,
    responses=TASK_RESPONSES,
)
async def get_task(
    task_id: UUID,
    service: TaskServiceDep,
    authorization: TaskAuthorizationDep,
    user: CurrentUserDep,
) -> Task:
    await authorization.require_task(user, task_id, write=False)
    return await service.get(task_id)


@tasks_router.patch(
    "/{task_id}",
    response_model=TaskRead,
    responses=TASK_RESPONSES,
)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    service: TaskServiceDep,
    authorization: TaskAuthorizationDep,
    user: CurrentUserDep,
) -> Task:
    await authorization.require_task(user, task_id, write=True)
    return await service.update(task_id, payload.to_changes())


@tasks_router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TASK_RESPONSES,
)
async def delete_task(
    task_id: UUID,
    service: TaskServiceDep,
    authorization: TaskAuthorizationDep,
    user: CurrentUserDep,
) -> Response:
    await authorization.require_task(user, task_id, write=True)
    await service.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
