from pathlib import Path


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


def test_dockerignore_coverage() -> None:
    dockerignore_path = Path(".dockerignore")
    assert dockerignore_path.is_file(), ".dockerignore must exist"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip()}
    assert ".git" in lines
    assert ".venv" in lines
    assert "__pycache__" in lines
    assert ".env" in lines


def test_compose_yaml_services() -> None:
    compose_path = Path("compose.yaml")
    assert compose_path.is_file(), "compose.yaml must exist"

    content = compose_path.read_text(encoding="utf-8")
    assert "services:" in content
    assert "db:" in content
    assert "redis:" in content
    assert "app:" in content
    assert "condition: service_healthy" in content
    assert "postgres:16" in content
    assert "redis:7" in content
