from app.application.passwords import hash_password, verify_password
from app.domain.user import User
from app.domain.user_repository import UserProfileChanges, UserRepository


class IncorrectPasswordError(Exception):
    pass


class ProfileService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def update(self, user: User, changes: UserProfileChanges) -> User:
        if not changes:
            return user
        return await self._users.update_profile(user.id, changes)

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not await verify_password(current_password, user.hashed_password):
            raise IncorrectPasswordError
        await self._users.update_password(user.id, await hash_password(new_password))
