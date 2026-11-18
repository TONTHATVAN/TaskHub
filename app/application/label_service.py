from uuid import UUID

from app.core.constants import LIMIT_DEFAULT, PAGE_DEFAULT
from app.domain.exceptions import LabelNotFoundError
from app.domain.label import Label
from app.domain.label_repository import LabelChanges, LabelRepository
from app.domain.task import Task


class LabelService:
    def __init__(self, repository: LabelRepository) -> None:
        self._repository = repository

    async def create(self, project_id: UUID, name: str, color: str) -> Label:
        return await self._repository.add(project_id, name, color)

    async def get(self, project_id: UUID, label_id: UUID) -> Label:
        label = await self._repository.get(project_id, label_id)
        if label is None:
            raise LabelNotFoundError
        return label

    async def list_by_project(
        self, project_id: UUID, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[Label], int]:
        return await self._repository.list_by_project(
            project_id, page=page, limit=limit
        )

    async def update(
        self, project_id: UUID, label_id: UUID, changes: LabelChanges
    ) -> Label:
        if not changes:
            return await self.get(project_id, label_id)
        label = await self._repository.save(project_id, label_id, changes)
        if label is None:
            raise LabelNotFoundError
        return label

    async def delete(self, project_id: UUID, label_id: UUID) -> None:
        if not await self._repository.delete(project_id, label_id):
            raise LabelNotFoundError

    async def attach(self, task: Task, label_id: UUID) -> None:
        if not await self._repository.attach(task.id, task.project_id, label_id):
            raise LabelNotFoundError

    async def detach(self, task: Task, label_id: UUID) -> None:
        if not await self._repository.detach(task.id, task.project_id, label_id):
            raise LabelNotFoundError

    async def list_for_task(self, task: Task) -> list[Label]:
        return await self._repository.list_for_task(task.id)
