from app.application.passwords import hash_password
from app.domain.user import User
from app.domain.user_repository import UserRepository


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def register(self, email: str, full_name: str, password: str) -> User:
        hashed_password = await hash_password(password)
        return await self._repository.add(email, full_name, hashed_password)
