from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import UserNotFoundError
from app.domain.user import User
from app.domain.user_repository import EmailAlreadyExistsError, UserProfileChanges
from app.infrastructure.models import UserModel
from app.infrastructure.repositories.base import BaseRepository


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = BaseRepository(session, UserModel)

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            hashed_password=model.hashed_password,
            role=model.role,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    async def get_by_email(self, email: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        return self._to_domain(model) if model is not None else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._repository.get(user_id)
        return self._to_domain(model) if model is not None else None

    async def get_by_id_for_update(self, user_id: UUID) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        )
        return self._to_domain(model) if model is not None else None

    async def add(self, email: str, full_name: str, hashed_password: str) -> User:
        model = UserModel(
            email=email, full_name=full_name, hashed_password=hashed_password
        )
        try:
            await self._repository.add(model)
        except IntegrityError as exc:
            raise EmailAlreadyExistsError from exc
        return self._to_domain(model)

    async def update_profile(self, user_id: UUID, changes: UserProfileChanges) -> User:
        try:
            result = await self._session.execute(
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(**changes)
                .returning(UserModel)
                .execution_options(populate_existing=True)
            )
        except IntegrityError as exc:
            raise EmailAlreadyExistsError from exc
        model = result.scalar_one_or_none()
        if model is None:
            raise UserNotFoundError
        return self._to_domain(model)

    async def update_password(self, user_id: UUID, hashed_password: str) -> None:
        result = await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(hashed_password=hashed_password)
            .returning(UserModel.id)
        )
        if result.scalar_one_or_none() is None:
            raise UserNotFoundError
