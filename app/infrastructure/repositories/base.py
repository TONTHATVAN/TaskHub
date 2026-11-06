from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import PAGINATION_OUT_OF_RANGE_MESSAGE
from app.infrastructure.models import Base

ModelT = TypeVar("ModelT", bound=Base)
EntityId = UUID | tuple[UUID, UUID]


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get(self, entity_id: EntityId) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(
        self, *, page: int = PAGE_DEFAULT, limit: int = LIMIT_DEFAULT
    ) -> tuple[list[ModelT], int]:
        if page < PAGE_MIN or not LIMIT_MIN <= limit <= LIMIT_MAX:
            raise ValueError(PAGINATION_OUT_OF_RANGE_MESSAGE)
        total = await self.session.scalar(select(func.count()).select_from(self.model))
        result = await self.session.scalars(
            select(self.model)
            .order_by(*self.model.__mapper__.primary_key)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result), total or 0

    async def save(self, entity: ModelT) -> ModelT:
        entity = await self.session.merge(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity_id: EntityId) -> bool:
        entity = await self.get(entity_id)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
