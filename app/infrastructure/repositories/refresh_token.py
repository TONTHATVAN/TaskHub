from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import RefreshTokenModel


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token_id: UUID, user_id: UUID, expires_at: datetime) -> None:
        self._session.add(
            RefreshTokenModel(id=token_id, user_id=user_id, expires_at=expires_at)
        )
        await self._session.flush()

    async def consume(self, token_id: UUID, user_id: UUID, now: datetime) -> bool:
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.id == token_id,
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
                RefreshTokenModel.expires_at > now,
            )
            .values(revoked_at=now)
            .returning(RefreshTokenModel.id)
        )
        return result.scalar_one_or_none() is not None
