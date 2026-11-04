import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_refresh_token_repository,
    get_token_service,
    get_user_repository,
)
from app.application.passwords import verify_password
from app.application.tokens import JwtTokenService
from app.domain.user import User, UserRole
from app.domain.user_repository import UserRepository
from app.main import create_app


class MemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

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


class MemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[UUID, tuple[UUID, datetime]] = {}

    async def add(self, token_id: UUID, user_id: UUID, expires_at: datetime) -> None:
        self.tokens[token_id] = (user_id, expires_at)

    async def consume(self, token_id: UUID, user_id: UUID, now: datetime) -> bool:
        stored = self.tokens.get(token_id)
        if stored is None or stored[0] != user_id or stored[1] <= now:
            return False
        del self.tokens[token_id]
        return True


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
        assert (
            repository.users["owner@example.com"].hashed_password != "secure-pass-123"
        )

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
        assert (
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": "user@example.com",
                    "full_name": "User",
                    "password": "secret-pass",
                },
            ).status_code
            == 201
        )

    async def check() -> None:
        user = await repository.get_by_email("user@example.com")
        assert user is not None
        assert await verify_password("secret-pass", user.hashed_password)
        assert not await verify_password("wrong-pass", user.hashed_password)

    asyncio.run(check())


def test_login_refresh_logout_and_profile() -> None:
    users = MemoryUserRepository()
    refresh_tokens = MemoryRefreshTokenRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_refresh_token_repository] = lambda: refresh_tokens
    app.dependency_overrides[get_token_service] = lambda: JwtTokenService(
        "test-secret" * 4, 15, 7
    )

    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "USER@EXAMPLE.COM",
                "full_name": "User",
                "password": "secret-pass",
            },
        )
        assert registered.status_code == 201

        assert client.get("/api/v1/users/me").status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "wrong"},
            ).status_code
            == 401
        )

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "USER@EXAMPLE.COM", "password": "secret-pass"},
        )
        assert login.status_code == 200
        pair = login.json()
        assert pair["token_type"] == "bearer"
        assert (
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {pair['access_token']}"},
            ).json()["id"]
            == registered.json()["id"]
        )

        assert (
            client.post(
                "/api/v1/auth/refresh", json={"refresh_token": pair["access_token"]}
            ).status_code
            == 401
        )
        refreshed = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert refreshed.status_code == 200
        new_pair = refreshed.json()
        assert new_pair["refresh_token"] != pair["refresh_token"]
        assert (
            client.post(
                "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            ).status_code
            == 401
        )

        assert (
            client.post(
                "/api/v1/auth/logout", json={"refresh_token": new_pair["refresh_token"]}
            ).status_code
            == 204
        )
        assert (
            client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": new_pair["refresh_token"]},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {new_pair['access_token']}"},
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/users/me", headers={"Authorization": "Bearer invalid"}
            ).status_code
            == 401
        )
        users.users["user@example.com"] = replace(
            users.users["user@example.com"], is_active=False
        )
        assert (
            client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {new_pair['access_token']}"},
            ).status_code
            == 401
        )


def test_expired_access_token_is_rejected() -> None:
    users = MemoryUserRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_token_service] = lambda: JwtTokenService(
        "test-secret" * 4, 15, 7
    )
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iss": "taskhub",
            "aud": "taskhub",
        },
        "test-secret" * 4,
        algorithm="HS256",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert response.status_code == 401
