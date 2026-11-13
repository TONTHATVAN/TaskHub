from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import (
    CommentServiceDep,
    CurrentUserDep,
    ReadableTaskDep,
    WritableTaskAccessDep,
    WritableTaskDep,
)
from app.api.v1.comment_schemas import CommentCreate, CommentRead
from app.api.v1.error_responses import (
    ARCHIVED_PROJECT_RESPONSES,
    TASK_RESPONSES,
    error_response,
)
from app.api.v1.pagination_schemas import PageRead
from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import COMMENT_NOT_FOUND_MESSAGE, TASK_NOT_FOUND_MESSAGE
from app.domain.comment import Comment

router = APIRouter(prefix="/tasks", tags=["comments"])
COMMENT_RESPONSES: dict[int | str, dict[str, Any]] = TASK_RESPONSES | {
    status.HTTP_404_NOT_FOUND: error_response(
        f"{TASK_NOT_FOUND_MESSAGE}; {COMMENT_NOT_FOUND_MESSAGE}"
    )
}


@router.post(
    "/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    responses=TASK_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def create_comment(
    task: WritableTaskDep,
    payload: CommentCreate,
    user: CurrentUserDep,
    service: CommentServiceDep,
) -> Comment:
    return await service.create(task, user, payload.content)


@router.get(
    "/{task_id}/comments",
    response_model=PageRead[CommentRead],
    responses=TASK_RESPONSES,
)
async def list_comments(
    task: ReadableTaskDep,
    service: CommentServiceDep,
    page: Annotated[int, Query(ge=PAGE_MIN)] = PAGE_DEFAULT,
    limit: Annotated[int, Query(ge=LIMIT_MIN, le=LIMIT_MAX)] = LIMIT_DEFAULT,
) -> dict[str, object]:
    items, total = await service.list_by_task(task, page=page, limit=limit)
    return {"items": items, "total": total, "page": page, "limit": limit}


@router.delete(
    "/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=COMMENT_RESPONSES | ARCHIVED_PROJECT_RESPONSES,
)
async def delete_comment(
    authorized: WritableTaskAccessDep,
    comment_id: UUID,
    user: CurrentUserDep,
    service: CommentServiceDep,
) -> Response:
    task, access = authorized
    await service.delete(task, access, comment_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
