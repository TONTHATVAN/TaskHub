from fastapi import APIRouter

from app.api.v1.tasks import projects_router, tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
