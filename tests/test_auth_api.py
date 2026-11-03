import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_user_repository
from app.application.passwords import verify_password
from app.domain.user import User, UserRole
from app.domain.user_repository import UserRepository
from app.main import create_app


class MemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def add(self, email: str, full_name: str, hashed_password: str) -> User:
        user = User(
            id=uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=UserRole.MEMBER,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.users[email] = user
        return user


def test_register_hashes_password_and_rejects_duplicate() -> None:
    repository = MemoryUserRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "Owner@Example.com",
                "full_name": "  Task Owner  ",
                "password": "secure-pass-123",
            },
        )
        assert response.status_code == 201
        assert response.json()["email"] == "owner@example.com"
        assert response.json()["full_name"] == "Task Owner"
        assert response.json()["role"] == "MEMBER"
        assert "password" not in response.json()
        assert "hashed_password" not in response.json()
        assert repository.users["owner@example.com"].hashed_password != "secure-pass-123"

        duplicate = client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner@example.com",
                "full_name": "Someone Else",
                "password": "secure-pass-456",
            },
        )
        assert duplicate.status_code == 409


def test_register_validates_password_and_email() -> None:
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: MemoryUserRepository()

    with TestClient(app) as client:
        for email, password in [
            ("invalid", "secure-pass-123"),
            ("user@example.com", "short"),
            ("user@example.com", "a" * 73),
            ("user@example.com", "đ" * 40),
        ]:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": email, "full_name": "User", "password": password},
            )
            assert response.status_code == 422


def test_password_hash_verification() -> None:
    repository: UserRepository = MemoryUserRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: repository

    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "full_name": "User", "password": "secret-pass"},
        ).status_code == 201

    async def check() -> None:
        user = await repository.get_by_email("user@example.com")
        assert user is not None
        assert await verify_password("secret-pass", user.hashed_password)
        assert not await verify_password("wrong-pass", user.hashed_password)

    asyncio.run(check())
