from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies import (
    ProjectServiceDep,
    ReadableProjectDep,
    WritableArchivedProjectDep,
    WritableProjectDep,
)
from app.api.v1.error_responses import (
    ARCHIVED_PROJECT_RESPONSES,
    PROJECT_RESPONSES,
)
from app.api.v1.project_schemas import ProjectRead, ProjectUpdate
from app.domain.project import Project

router = APIRouter(prefix="/projects", tags=["projects"])
PROJECT_WRITE_RESPONSES = PROJECT_RESPONSES | ARCHIVED_PROJECT_RESPONSES


@router.get("/{project_id}", response_model=ProjectRead, responses=PROJECT_RESPONSES)
async def get_project(
    project_id: UUID,
    access: ReadableProjectDep,
    service: ProjectServiceDep,
) -> Project:
    return await service.get(project_id)


@router.patch(
    "/{project_id}", response_model=ProjectRead, responses=PROJECT_WRITE_RESPONSES
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    access: WritableProjectDep,
    service: ProjectServiceDep,
) -> Project:
    return await service.update(project_id, payload.to_changes())


@router.post(
    "/{project_id}/archive", response_model=ProjectRead, responses=PROJECT_RESPONSES
)
async def archive_project(
    project_id: UUID,
    access: WritableArchivedProjectDep,
    service: ProjectServiceDep,
) -> Project:
    return await service.archive(project_id)


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, responses=PROJECT_RESPONSES
)
async def delete_project(
    project_id: UUID,
    access: WritableArchivedProjectDep,
    service: ProjectServiceDep,
) -> Response:
    await service.delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
