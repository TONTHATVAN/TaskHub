from typing import Protocol
from uuid import UUID

from app.domain.user import User


class EmailAlreadyExistsError(Exception):
    pass


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, email: str, full_name: str, hashed_password: str) -> User: ...
