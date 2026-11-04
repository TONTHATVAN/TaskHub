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
