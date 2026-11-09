from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUserDep, WorkspaceServiceDep
from app.api.v1.error_responses import ACCESS_DENIED_RESPONSES, UNAUTHORIZED_RESPONSES
from app.api.v1.error_schemas import ErrorRead
from app.api.v1.workspace_schemas import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.core.messages import WORKSPACE_NOT_FOUND_MESSAGE
from app.domain.workspace import Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
WORKSPACE_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorRead,
        "description": WORKSPACE_NOT_FOUND_MESSAGE,
    }
}
WORKSPACE_RESPONSES = (
    WORKSPACE_NOT_FOUND_RESPONSES | ACCESS_DENIED_RESPONSES | UNAUTHORIZED_RESPONSES
)


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
