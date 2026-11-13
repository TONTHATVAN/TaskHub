from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class RefreshConsumeResult(StrEnum):
    CONSUMED = "consumed"
    REPLAYED = "replayed"
    INVALID = "invalid"


class RefreshTokenRepository(Protocol):
    async def add(
        self, token_id: UUID, user_id: UUID, expires_at: datetime
    ) -> None: ...

    async def consume(
        self, token_id: UUID, user_id: UUID, now: datetime
    ) -> RefreshConsumeResult: ...

    async def revoke_all(self, user_id: UUID, now: datetime) -> None: ...
