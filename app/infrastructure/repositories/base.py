from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import NotFoundError
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

    async def list(self, *, page: int = 1, limit: int = 20) -> tuple[list[ModelT], int]:
        if page < 1 or not 1 <= limit <= 100:
            raise ValueError("page and limit are out of range")
        total = await self.session.scalar(select(func.count()).select_from(self.model))
        result = await self.session.scalars(
            select(self.model)
            .order_by(*self.model.__mapper__.primary_key)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result), total or 0

    async def save(self, entity: ModelT) -> ModelT:
        key_columns = inspect(self.model).primary_key
        key_values = tuple(getattr(entity, column.name) for column in key_columns)
        if any(value is None for value in key_values):
            raise NotFoundError(f"{self.model.__name__} primary key is required")

        values = {
            column.name: getattr(entity, column.name)
            for column in inspect(self.model).columns
            if not column.primary_key
        }
        # A managed, dirty instance would otherwise flush before the explicit UPDATE.
        if inspect(entity).session is self.session.sync_session:
            self.session.expunge(entity)
        result = await self.session.execute(
            update(self.model)
            .where(*(column == value for column, value in zip(key_columns, key_values)))
            .values(**values)
            .returning(*key_columns)
        )
        if result.first() is None:
            raise NotFoundError(f"{self.model.__name__} not found")
        entity_id = key_values[0] if len(key_values) == 1 else key_values
        saved = await self.get(entity_id)
        assert saved is not None
        return saved

    async def delete(self, entity_id: EntityId) -> bool:
        key_columns = inspect(self.model).primary_key
        key_values = entity_id if isinstance(entity_id, tuple) else (entity_id,)
        result = await self.session.execute(
            delete(self.model)
            .where(*(column == value for column, value in zip(key_columns, key_values)))
            .returning(*key_columns)
        )
        return result.first() is not None
