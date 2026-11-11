from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.refresh_token_repository import RefreshConsumeResult
from app.infrastructure.models import RefreshTokenModel


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token_id: UUID, user_id: UUID, expires_at: datetime) -> None:
        self._session.add(
            RefreshTokenModel(id=token_id, user_id=user_id, expires_at=expires_at)
        )
        await self._session.flush()

    async def consume(
        self, token_id: UUID, user_id: UUID, now: datetime
    ) -> RefreshConsumeResult:
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
        if result.scalar_one_or_none() is not None:
            return RefreshConsumeResult.CONSUMED
        stored = (
            await self._session.execute(
                select(RefreshTokenModel.revoked_at).where(
                    RefreshTokenModel.id == token_id,
                    RefreshTokenModel.user_id == user_id,
                )
            )
        ).one_or_none()
        if stored is not None and stored.revoked_at is not None:
            return RefreshConsumeResult.REPLAYED
        return RefreshConsumeResult.INVALID

    async def revoke_all(self, user_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
