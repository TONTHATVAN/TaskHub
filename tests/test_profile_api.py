from fastapi.testclient import TestClient
from test_auth_api import MemoryRefreshTokenRepository, MemoryUserRepository

from app.api.dependencies import (
    get_refresh_token_repository,
    get_token_service,
    get_user_repository,
)
from app.application.tokens import JwtTokenService
from app.main import create_app


def test_profile_update_and_password_change() -> None:
    users = MemoryUserRepository()
    refresh_tokens = MemoryRefreshTokenRepository()
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_refresh_token_repository] = lambda: refresh_tokens
    app.dependency_overrides[get_token_service] = lambda: JwtTokenService(
        "test-secret" * 4, 15, 7
    )

    with TestClient(app) as client:
        for email in ("first@example.com", "second@example.com"):
            assert (
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "full_name": "Original",
                        "password": "old-password",
                    },
                ).status_code
                == 201
            )

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "first@example.com", "password": "old-password"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        old_refresh_token = login.json()["refresh_token"]
        second_login = client.post(
            "/api/v1/auth/login",
            json={"email": "first@example.com", "password": "old-password"},
        )
        assert second_login.status_code == 200
        second_refresh_token = second_login.json()["refresh_token"]

        assert (
            client.patch("/api/v1/users/me", json={"full_name": "Guest"}).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "old-password",
                    "new_password": "new-password",
                },
            ).status_code
            == 401
        )

        for payload in (
            {"email": None},
            {"role": "ADMIN"},
            {"full_name": None},
            {"full_name": "  "},
            {"full_name": "x" * 201},
            {"full_name": 123},
            {"email": "invalid"},
            {"email": f"{'a' * 310}@example.com"},
        ):
            assert (
                client.patch(
                    "/api/v1/users/me", json=payload, headers=headers
                ).status_code
                == 422
            )

        duplicate = client.patch(
            "/api/v1/users/me",
            json={"email": "second@example.com"},
            headers=headers,
        )
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "Email already registered"}
        assert (
            client.get("/api/v1/users/me", headers=headers).json()["email"]
            == "first@example.com"
        )

        name_only = client.patch(
            "/api/v1/users/me", json={"full_name": "  Only Name  "}, headers=headers
        )
        assert name_only.status_code == 200
        assert name_only.json()["full_name"] == "Only Name"
        assert name_only.json()["email"] == "first@example.com"

        email_only = client.patch(
            "/api/v1/users/me",
            json={"email": "only.email@example.com"},
            headers=headers,
        )
        assert email_only.status_code == 200
        assert email_only.json()["email"] == "only.email@example.com"
        assert email_only.json()["full_name"] == "Only Name"

        updated = client.patch(
            "/api/v1/users/me",
            json={"email": "FIRST.NEW@EXAMPLE.COM", "full_name": "  New Name  "},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["email"] == "first.new@example.com"
        assert updated.json()["full_name"] == "New Name"
        assert "hashed_password" not in updated.json()
        assert (
            client.get("/api/v1/users/me", headers=headers).json()["email"]
            == "first.new@example.com"
        )

        endpoint = "/api/v1/users/me/change-password"
        for new_password in ("short", "a" * 73, "đ" * 40):
            assert (
                client.post(
                    endpoint,
                    json={
                        "current_password": "old-password",
                        "new_password": new_password,
                    },
                    headers=headers,
                ).status_code
                == 422
            )
        assert (
            client.post(
                endpoint,
                json={"current_password": "đ" * 40, "new_password": "new-password"},
                headers=headers,
            ).status_code
            == 422
        )
        wrong_current = client.post(
            endpoint,
            json={"current_password": "wrong", "new_password": "new-password"},
            headers=headers,
        )
        assert wrong_current.status_code == 400
        assert wrong_current.json() == {"detail": "Current password is incorrect"}
        assert (
            client.post(
                endpoint,
                json={
                    "current_password": "old-password",
                    "new_password": "new-password",
                },
                headers=headers,
            ).status_code
            == 204
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "first.new@example.com", "password": "old-password"},
            ).status_code
            == 401
        )
        for refresh_token in (old_refresh_token, second_refresh_token):
            revoked_refresh = client.post(
                "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
            )
            assert revoked_refresh.status_code == 401
            assert revoked_refresh.headers["WWW-Authenticate"] == "Bearer"
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "first.new@example.com", "password": "new-password"},
            ).status_code
            == 200
        )
