from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_api_documentation() -> None:
    app = create_app()
    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"]["type"] == "http"
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/refresh" in schema["paths"]
    assert "/api/v1/auth/logout" in schema["paths"]
    assert "/api/v1/users/me" in schema["paths"]

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


def test_auth_and_profile_errors_are_documented() -> None:
    paths = create_app().openapi()["paths"]
    expected = (
        ("/api/v1/auth/register", "post", "409"),
        ("/api/v1/auth/login", "post", "401"),
        ("/api/v1/auth/refresh", "post", "401"),
        ("/api/v1/auth/logout", "post", "401"),
        ("/api/v1/users/me", "get", "401"),
        ("/api/v1/users/me", "patch", "409"),
        ("/api/v1/users/me/change-password", "post", "400"),
    )
    for path, method, status_code in expected:
        response = paths[path][method]["responses"][status_code]
        assert response["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorRead"
        }
    for path, method in (
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/refresh", "post"),
        ("/api/v1/auth/logout", "post"),
        ("/api/v1/users/me", "get"),
    ):
        assert "WWW-Authenticate" in paths[path][method]["responses"]["401"]["headers"]
