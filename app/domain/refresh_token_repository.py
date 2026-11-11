from datetime import datetime
from typing import Protocol
from uuid import UUID


class RefreshTokenRepository(Protocol):
    async def add(
        self, token_id: UUID, user_id: UUID, expires_at: datetime
    ) -> None: ...

    async def consume(self, token_id: UUID, user_id: UUID, now: datetime) -> bool: ...

    async def revoke_all(self, user_id: UUID, now: datetime) -> None: ...
