from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import TaskServiceDep
from app.api.v1.task_schemas import TaskCreate, TaskRead, TaskUpdate
from app.application.task_service import ProjectNotFoundError
from app.domain.task import Task

projects_router = APIRouter(prefix="/projects", tags=["tasks"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


@projects_router.post(
    "/{project_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED
)
async def create_task(
    project_id: UUID, payload: TaskCreate, service: TaskServiceDep
) -> Task:
    try:
        return await service.create(
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@projects_router.get("/{project_id}/tasks", response_model=list[TaskRead])
async def list_tasks(
    project_id: UUID,
    service: TaskServiceDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[Task]:
    return await service.list_by_project(project_id, page=page, limit=limit)


@tasks_router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: UUID, service: TaskServiceDep) -> Task:
    task = await service.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@tasks_router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID, payload: TaskUpdate, service: TaskServiceDep
) -> Task:
    task = await service.update(task_id, payload.to_changes())
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@tasks_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, service: TaskServiceDep) -> Response:
    deleted = await service.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
