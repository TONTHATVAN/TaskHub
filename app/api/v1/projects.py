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
    project: ReadableProjectDep,
) -> Project:
    return project


@router.patch(
    "/{project_id}", response_model=ProjectRead, responses=PROJECT_WRITE_RESPONSES
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    project: WritableProjectDep,
    service: ProjectServiceDep,
) -> Project:
    changes = payload.to_changes()
    return await service.update(project.id, changes) if changes else project


@router.post(
    "/{project_id}/archive", response_model=ProjectRead, responses=PROJECT_RESPONSES
)
async def archive_project(
    project_id: UUID,
    project: WritableArchivedProjectDep,
    service: ProjectServiceDep,
) -> Project:
    return await service.archive(project.id)


@router.post(
    "/{project_id}/unarchive", response_model=ProjectRead, responses=PROJECT_RESPONSES
)
async def unarchive_project(
    project: WritableArchivedProjectDep,
    service: ProjectServiceDep,
) -> Project:
    return await service.unarchive(project.id)


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, responses=PROJECT_RESPONSES
)
async def delete_project(
    project_id: UUID,
    project: WritableArchivedProjectDep,
    service: ProjectServiceDep,
) -> Response:
    await service.delete(project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
