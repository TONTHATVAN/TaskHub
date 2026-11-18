from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.labels import projects_router as label_projects_router
from app.api.v1.labels import tasks_router as label_tasks_router
from app.api.v1.projects import router as project_router
from app.api.v1.tasks import projects_router, tasks_router
from app.api.v1.users import router as users_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(project_router)
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
api_router.include_router(label_projects_router)
api_router.include_router(label_tasks_router)
api_router.include_router(users_router)
api_router.include_router(workspaces_router)
