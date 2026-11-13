from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import (
    ReadableProjectDep,
    ReadableTaskDep,
    TaskServiceDep,
    WritableProjectDep,
    WritableTaskDep,
)
from app.api.v1.error_responses import (
    ARCHIVED_PROJECT_RESPONSES,
    PROJECT_RESPONSES,
    TASK_RESPONSES,
)
from app.api.v1.task_schemas import TaskCreate, TaskRead, TaskUpdate
from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.domain.task import Task

projects_router = APIRouter(prefix="/projects", tags=["tasks"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


@projects_router.post(
    "/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    responses=PROJECT_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    access: WritableProjectDep,
    service: TaskServiceDep,
) -> Task:
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
    access: ReadableProjectDep,
    service: TaskServiceDep,
    page: Annotated[int, Query(ge=PAGE_MIN)] = PAGE_DEFAULT,
    limit: Annotated[int, Query(ge=LIMIT_MIN, le=LIMIT_MAX)] = LIMIT_DEFAULT,
) -> list[Task]:
    return await service.list_by_project(project_id, page=page, limit=limit)


@tasks_router.get(
    "/{task_id}",
    response_model=TaskRead,
    responses=TASK_RESPONSES,
)
async def get_task(
    task: ReadableTaskDep,
) -> Task:
    return task


@tasks_router.patch(
    "/{task_id}",
    response_model=TaskRead,
    responses=TASK_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def update_task(
    payload: TaskUpdate,
    task: WritableTaskDep,
    service: TaskServiceDep,
) -> Task:
    return await service.update(task, payload.to_changes())


@tasks_router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TASK_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def delete_task(
    task: WritableTaskDep,
    service: TaskServiceDep,
) -> Response:
    await service.delete(task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
