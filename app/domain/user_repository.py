from typing import Protocol, TypedDict
from uuid import UUID

from app.domain.user import User


class EmailAlreadyExistsError(Exception):
    pass


class UserProfileChanges(TypedDict, total=False):
    email: str
    full_name: str


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_id_for_update(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, email: str, full_name: str, hashed_password: str) -> User: ...

    async def update_profile(
        self, user_id: UUID, changes: UserProfileChanges
    ) -> User: ...

    async def update_password(self, user_id: UUID, hashed_password: str) -> None: ...
