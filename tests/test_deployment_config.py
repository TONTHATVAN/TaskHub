from pathlib import Path

import yaml  # type: ignore[import-untyped]


def test_dockerfile_multi_stage_structure() -> None:
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.is_file(), "Dockerfile must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim AS builder" in content
    assert "FROM python:3.12-slim AS runner" in content
    assert "USER taskhub" in content
    assert "EXPOSE 8000" in content
    assert "alembic upgrade head" in content
    assert "uvicorn app.main:app" in content
    assert "COPY requirements.txt" in content
    assert "requirements-dev.txt" not in content


def test_runtime_requirements_exclude_development_tools() -> None:
    runtime = Path("requirements.txt").read_text(encoding="utf-8").lower()
    development = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
    assert "-r requirements.txt" in development
    for package in ("ruff==", "mypy==", "pytest==", "httpx==", "pyyaml=="):
        assert package not in runtime
        assert package in development


def test_dockerignore_coverage() -> None:
    dockerignore_path = Path(".dockerignore")
    assert dockerignore_path.is_file(), ".dockerignore must exist"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip()}
    assert ".git" in lines
    assert ".venv" in lines
    assert "__pycache__" in lines
    assert ".env" in lines
    assert ".env.*" in lines


def test_compose_yaml_services() -> None:
    compose_path = Path("compose.yaml")
    assert compose_path.is_file(), "compose.yaml must exist"

    content = compose_path.read_text(encoding="utf-8")
    config = yaml.safe_load(content)
    services = config["services"]
    assert set(services) == {"app", "db", "redis", "mailpit"}
    assert services["app"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert services["app"]["depends_on"]["redis"]["condition"] == "service_healthy"
    assert services["app"]["ports"] == ["127.0.0.1:8000:8000"]
    assert services["db"]["image"] == "postgres:16"
    assert services["redis"]["image"] == "redis:7"
    assert services["mailpit"]["image"] == "axllent/mailpit:v1.34.0"
    assert "${POSTGRES_PASSWORD:?" in services["db"]["environment"]["POSTGRES_PASSWORD"]
    assert "${POSTGRES_PASSWORD:?" in services["app"]["environment"]["DATABASE_URL"]
    assert "${JWT_SECRET_KEY:?" in services["app"]["environment"]["JWT_SECRET_KEY"]


def test_example_env_requires_generated_secrets() -> None:
    entries = dict(
        line.split("=", 1)
        for line in Path(".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert entries["POSTGRES_PASSWORD"] == ""
    assert entries["JWT_SECRET_KEY"] == ""
    assert "replace-with-a-local-password" in entries["DATABASE_URL"]
