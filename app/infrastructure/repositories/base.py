from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    PAGE_DEFAULT,
    PAGE_MIN,
)
from app.core.messages import (
    ENTITY_NOT_FOUND_TEMPLATE,
    ENTITY_PRIMARY_KEY_REQUIRED_MESSAGE,
    PAGINATION_OUT_OF_RANGE_MESSAGE,
)
from app.domain.exceptions import NotFoundError
from app.infrastructure.models import Base

ModelT = TypeVar("ModelT", bound=Base)
EntityId = UUID | tuple[UUID, UUID]


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def _key_values(self, entity_id: EntityId) -> tuple[UUID, ...]:
        values = entity_id if isinstance(entity_id, tuple) else (entity_id,)
        if len(values) != len(inspect(self.model).primary_key) or any(
            value is None for value in values
        ):
            raise ValueError(ENTITY_PRIMARY_KEY_REQUIRED_MESSAGE)
        return values

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get(self, entity_id: EntityId) -> ModelT | None:
        self._key_values(entity_id)
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
        key_columns = inspect(self.model).primary_key
        key_values = tuple(getattr(entity, column.name) for column in key_columns)
        if any(value is None for value in key_values):
            raise ValueError(ENTITY_PRIMARY_KEY_REQUIRED_MESSAGE)

        state = inspect(entity)
        values = {
            column.name: getattr(entity, column.name)
            for column in inspect(self.model).columns
            if not column.primary_key and state.attrs[column.name].history.has_changes()
        }
        # A managed, dirty instance would otherwise flush before the explicit UPDATE.
        if state.session is self.session.sync_session:
            self.session.expunge(entity)
        predicate = tuple(
            column == value for column, value in zip(key_columns, key_values)
        )
        if values:
            result = await self.session.execute(
                update(self.model)
                .where(*predicate)
                .values(**values)
                .returning(*key_columns)
            )
            found = result.first() is not None
        else:
            found = (
                await self.session.execute(select(*key_columns).where(*predicate))
            ).first() is not None
        if not found:
            raise NotFoundError(
                ENTITY_NOT_FOUND_TEMPLATE.format(entity=self.model.__name__)
            )
        entity_id = key_values[0] if len(key_values) == 1 else key_values
        saved = await self.get(entity_id)
        assert saved is not None
        return saved

    async def delete(self, entity_id: EntityId) -> bool:
        key_columns = inspect(self.model).primary_key
        key_values = self._key_values(entity_id)
        result = await self.session.execute(
            delete(self.model)
            .where(*(column == value for column, value in zip(key_columns, key_values)))
            .returning(*key_columns)
        )
        return result.first() is not None
