from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import (
    CurrentUserDep,
    ProjectServiceDep,
    ReadableWorkspaceDep,
    WorkspaceServiceDep,
    WritableWorkspaceDep,
)
from app.api.v1.error_responses import (
    UNAUTHORIZED_RESPONSES,
    WORKSPACE_RESPONSES,
    error_response,
)
from app.api.v1.project_schemas import ProjectCreate, ProjectRead
from app.api.v1.workspace_schemas import (
    WorkspaceCreate,
    WorkspaceMemberInvite,
    WorkspaceMemberRead,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import (
    INACTIVE_WORKSPACE_MEMBER_MESSAGE,
    USER_NOT_FOUND_MESSAGE,
    WORKSPACE_MEMBER_EXISTS_MESSAGE,
    WORKSPACE_MEMBER_NOT_FOUND_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)
from app.domain.project import Project
from app.domain.workspace import Workspace, WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
MEMBER_INVITE_RESPONSES: dict[int | str, dict[str, Any]] = WORKSPACE_RESPONSES | {
    status.HTTP_404_NOT_FOUND: error_response(
        f"{WORKSPACE_NOT_FOUND_MESSAGE}; {USER_NOT_FOUND_MESSAGE}"
    ),
    status.HTTP_409_CONFLICT: error_response(
        f"{WORKSPACE_MEMBER_EXISTS_MESSAGE}; {INACTIVE_WORKSPACE_MEMBER_MESSAGE}"
    ),
}
MEMBER_REMOVE_RESPONSES: dict[int | str, dict[str, Any]] = WORKSPACE_RESPONSES | {
    status.HTTP_404_NOT_FOUND: error_response(
        f"{WORKSPACE_NOT_FOUND_MESSAGE}; {WORKSPACE_MEMBER_NOT_FOUND_MESSAGE}"
    ),
}


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    responses=UNAUTHORIZED_RESPONSES,
)
async def create_workspace(
    payload: WorkspaceCreate, user: CurrentUserDep, service: WorkspaceServiceDep
) -> Workspace:
    return await service.create(user, payload.name)


@router.get(
    "/{workspace_id}", response_model=WorkspaceRead, responses=WORKSPACE_RESPONSES
)
async def get_workspace(
    workspace_id: UUID, user: CurrentUserDep, service: WorkspaceServiceDep
) -> Workspace:
    return await service.get(user, workspace_id)


@router.patch(
    "/{workspace_id}", response_model=WorkspaceRead, responses=WORKSPACE_RESPONSES
)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdate,
    user: CurrentUserDep,
    service: WorkspaceServiceDep,
) -> Workspace:
    return await service.rename(user, workspace_id, payload.name)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=WORKSPACE_RESPONSES,
)
async def delete_workspace(
    workspace_id: UUID, user: CurrentUserDep, service: WorkspaceServiceDep
) -> Response:
    await service.delete(user, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberRead],
    responses=WORKSPACE_RESPONSES,
)
async def list_workspace_members(
    workspace_id: UUID, user: CurrentUserDep, service: WorkspaceServiceDep
) -> list[WorkspaceMember]:
    return await service.list_members(user, workspace_id)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberRead,
    status_code=status.HTTP_201_CREATED,
    responses=MEMBER_INVITE_RESPONSES,
)
async def invite_workspace_member(
    workspace_id: UUID,
    payload: WorkspaceMemberInvite,
    user: CurrentUserDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMember:
    return await service.invite_member(
        user, workspace_id, payload.user_id, payload.role
    )


@router.delete(
    "/{workspace_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=MEMBER_REMOVE_RESPONSES,
)
async def remove_workspace_member(
    workspace_id: UUID,
    member_id: UUID,
    user: CurrentUserDep,
    service: WorkspaceServiceDep,
) -> Response:
    await service.remove_member(user, workspace_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    responses=WORKSPACE_RESPONSES,
)
async def create_project(
    workspace: WritableWorkspaceDep,
    payload: ProjectCreate,
    projects: ProjectServiceDep,
) -> Project:
    return await projects.create(workspace.id, payload.name, payload.description)


@router.get(
    "/{workspace_id}/projects",
    response_model=list[ProjectRead],
    responses=WORKSPACE_RESPONSES,
)
async def list_projects(
    workspace: ReadableWorkspaceDep,
    projects: ProjectServiceDep,
    page: Annotated[int, Query(ge=PAGE_MIN)] = PAGE_DEFAULT,
    limit: Annotated[int, Query(ge=LIMIT_MIN, le=LIMIT_MAX)] = LIMIT_DEFAULT,
) -> list[Project]:
    return await projects.list_by_workspace(workspace.id, page=page, limit=limit)
