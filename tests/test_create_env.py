import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_env.py"
TEMPLATE = Path(__file__).resolve().parents[1] / ".env.example"


def run_script(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def read_env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def test_create_env_generates_secrets_and_preserves_existing_file(
    tmp_path: Path,
) -> None:
    shutil.copyfile(TEMPLATE, tmp_path / ".env.example")

    result = run_script(tmp_path)
    assert result.returncode == 0, result.stderr
    created = tmp_path / ".env"
    values = read_env(created)
    assert len(values["POSTGRES_PASSWORD"]) >= 32
    assert len(values["JWT_SECRET_KEY"]) >= 32
    assert urlsplit(values["DATABASE_URL"]).password == values["POSTGRES_PASSWORD"]

    original = created.read_bytes()
    assert run_script(tmp_path).returncode == 0
    assert created.read_bytes() == original


def test_create_env_does_not_depend_on_example_password_text(tmp_path: Path) -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    database_url = read_env(TEMPLATE)["DATABASE_URL"]
    old_password = urlsplit(database_url).password
    assert old_password is not None
    template = template.replace(old_password, "another-placeholder")
    (tmp_path / ".env.example").write_text(template, encoding="utf-8")

    assert run_script(tmp_path).returncode == 0
    values = read_env(tmp_path / ".env")
    assert urlsplit(values["DATABASE_URL"]).password == values["POSTGRES_PASSWORD"]


def test_create_env_rejects_missing_key_without_writing_file(tmp_path: Path) -> None:
    template = "\n".join(
        line
        for line in TEMPLATE.read_text(encoding="utf-8").splitlines()
        if line.partition("=")[0] != "JWT_SECRET_KEY"
    )
    (tmp_path / ".env.example").write_text(template, encoding="utf-8")

    result = run_script(tmp_path)
    assert result.returncode != 0
    assert "JWT_SECRET_KEY" in result.stderr
    assert not (tmp_path / ".env").exists()


def test_create_env_rejects_existing_public_default(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "POSTGRES_USER=taskhub\n"
        "POSTGRES_PASSWORD=taskhub\n"
        "POSTGRES_DB=taskhub\n"
        "DATABASE_URL=postgresql+asyncpg://taskhub:taskhub@localhost:5433/taskhub\n"
        "JWT_SECRET_KEY=taskhub-default-jwt-secret-key-32-chars-min\n",
        encoding="utf-8",
    )

    result = run_script(tmp_path)
    assert result.returncode != 0
    assert "POSTGRES_PASSWORD" in result.stderr


def test_create_env_rejects_existing_mismatched_database_user(tmp_path: Path) -> None:
    shutil.copyfile(TEMPLATE, tmp_path / ".env.example")
    assert run_script(tmp_path).returncode == 0

    existing = tmp_path / ".env"
    content = "\n".join(
        "POSTGRES_USER=another-user"
        if line.partition("=")[0] == "POSTGRES_USER"
        else line
        for line in existing.read_text(encoding="utf-8").splitlines()
    )
    existing.write_text(content, encoding="utf-8")

    result = run_script(tmp_path)
    assert result.returncode != 0
    assert "POSTGRES_USER" in result.stderr
