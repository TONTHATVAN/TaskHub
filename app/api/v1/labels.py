from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import (
    LabelServiceDep,
    ReadableProjectDep,
    ReadableTaskDep,
    WritableProjectDep,
    WritableTaskDep,
)
from app.api.v1.error_responses import (
    ARCHIVED_PROJECT_RESPONSES,
    PROJECT_RESPONSES,
    TASK_RESPONSES,
    error_response,
)
from app.api.v1.label_schemas import LabelCreate, LabelRead, LabelUpdate
from app.api.v1.pagination_schemas import PageRead
from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import (
    LABEL_ALREADY_EXISTS_MESSAGE,
    LABEL_NOT_FOUND_MESSAGE,
    PROJECT_ARCHIVED_MESSAGE,
    PROJECT_NOT_FOUND_MESSAGE,
    TASK_NOT_FOUND_MESSAGE,
)
from app.domain.label import Label

projects_router = APIRouter(prefix="/projects", tags=["labels"])
tasks_router = APIRouter(prefix="/tasks", tags=["labels"])

PROJECT_LABEL_RESPONSES: dict[int | str, dict[str, Any]] = PROJECT_RESPONSES | {
    status.HTTP_404_NOT_FOUND: error_response(
        f"{PROJECT_NOT_FOUND_MESSAGE}; {LABEL_NOT_FOUND_MESSAGE}"
    )
}
LABEL_WRITE_RESPONSES = (
    PROJECT_LABEL_RESPONSES
    | ARCHIVED_PROJECT_RESPONSES
    | {
        status.HTTP_409_CONFLICT: error_response(
            f"{PROJECT_ARCHIVED_MESSAGE}; {LABEL_ALREADY_EXISTS_MESSAGE}"
        )
    }
)
TASK_LABEL_RESPONSES = TASK_RESPONSES | {
    status.HTTP_404_NOT_FOUND: error_response(
        f"{TASK_NOT_FOUND_MESSAGE}; {LABEL_NOT_FOUND_MESSAGE}"
    )
}


@projects_router.post(
    "/{project_id}/labels",
    response_model=LabelRead,
    status_code=status.HTTP_201_CREATED,
    responses=LABEL_WRITE_RESPONSES,
)
async def create_label(
    project: WritableProjectDep, payload: LabelCreate, service: LabelServiceDep
) -> Label:
    return await service.create(project.id, payload.name, payload.color)


@projects_router.get(
    "/{project_id}/labels",
    response_model=PageRead[LabelRead],
    responses=PROJECT_RESPONSES,
)
async def list_labels(
    project: ReadableProjectDep,
    service: LabelServiceDep,
    page: Annotated[int, Query(ge=PAGE_MIN)] = PAGE_DEFAULT,
    limit: Annotated[int, Query(ge=LIMIT_MIN, le=LIMIT_MAX)] = LIMIT_DEFAULT,
) -> dict[str, object]:
    items, total = await service.list_by_project(project.id, page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@projects_router.get(
    "/{project_id}/labels/{label_id}",
    response_model=LabelRead,
    responses=PROJECT_LABEL_RESPONSES,
)
async def get_label(
    project: ReadableProjectDep, label_id: UUID, service: LabelServiceDep
) -> Label:
    return await service.get(project.id, label_id)


@projects_router.patch(
    "/{project_id}/labels/{label_id}",
    response_model=LabelRead,
    responses=LABEL_WRITE_RESPONSES,
)
async def update_label(
    project: WritableProjectDep,
    label_id: UUID,
    payload: LabelUpdate,
    service: LabelServiceDep,
) -> Label:
    return await service.update(project.id, label_id, payload.to_changes())


@projects_router.delete(
    "/{project_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=PROJECT_LABEL_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def delete_label(
    project: WritableProjectDep, label_id: UUID, service: LabelServiceDep
) -> Response:
    await service.delete(project.id, label_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@tasks_router.get(
    "/{task_id}/labels", response_model=list[LabelRead], responses=TASK_RESPONSES
)
async def list_task_labels(
    task: ReadableTaskDep, service: LabelServiceDep
) -> list[Label]:
    return await service.list_for_task(task)


@tasks_router.post(
    "/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TASK_LABEL_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def attach_label(
    task: WritableTaskDep, label_id: UUID, service: LabelServiceDep
) -> Response:
    await service.attach(task, label_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@tasks_router.delete(
    "/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=TASK_LABEL_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def detach_label(
    task: WritableTaskDep, label_id: UUID, service: LabelServiceDep
) -> Response:
    await service.detach(task, label_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
