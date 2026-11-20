"""Create a local .env with random secrets from .env.example."""

import secrets
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

REQUIRED_KEYS = frozenset(
    {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "DATABASE_URL",
        "JWT_SECRET_KEY",
    }
)


def read_entries(lines: list[str]) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key or key in entries:
            raise ValueError("Invalid or duplicate key in environment file")
        entries[key] = value
    return entries


def database_url_with_password(
    url: str, user: str, database: str, password: str
) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "postgresql+asyncpg"
        or parsed.username != user
        or parsed.hostname is None
        or parsed.port is None
        or parsed.path != f"/{database}"
    ):
        raise ValueError(
            "DATABASE_URL in .env.example must match POSTGRES_USER and POSTGRES_DB"
        )
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return urlunsplit(parsed._replace(netloc=f"{user}:{password}@{host}:{parsed.port}"))


def validate_existing(entries: dict[str, str]) -> None:
    missing = REQUIRED_KEYS - entries.keys()
    if missing:
        raise ValueError(f"Missing required keys in .env: {', '.join(sorted(missing))}")

    password = entries.get("POSTGRES_PASSWORD", "")
    secret = entries.get("JWT_SECRET_KEY", "")
    if not password or password == "taskhub" or password.startswith("replace-with-"):
        raise ValueError("POSTGRES_PASSWORD must be set to a private password")
    if (
        len(secret) < 32
        or secret.startswith("replace-with-")
        or secret == "taskhub-default-jwt-secret-key-32-chars-min"
    ):
        raise ValueError(
            "JWT_SECRET_KEY must be set to a private secret of at least 32 characters"
        )
    parsed = urlsplit(entries.get("DATABASE_URL", ""))
    if (
        not entries["POSTGRES_USER"]
        or not entries["POSTGRES_DB"]
        or parsed.scheme != "postgresql+asyncpg"
        or parsed.username != entries["POSTGRES_USER"]
        or parsed.hostname is None
        or parsed.port is None
        or parsed.path != f"/{entries['POSTGRES_DB']}"
    ):
        raise ValueError("DATABASE_URL must match POSTGRES_USER and POSTGRES_DB")
    if unquote(parsed.password or "") != password:
        raise ValueError("DATABASE_URL password must match POSTGRES_PASSWORD")


def create_env(template: Path, target: Path) -> bool:
    if target.exists():
        validate_existing(
            read_entries(target.read_text(encoding="utf-8-sig").splitlines())
        )
        return False

    lines = template.read_text(encoding="utf-8-sig").splitlines()
    entries = read_entries(lines)
    missing = REQUIRED_KEYS - entries.keys()
    if missing:
        raise ValueError(
            f"Missing required keys in .env.example: {', '.join(sorted(missing))}"
        )

    password = secrets.token_hex(24)
    secret = secrets.token_urlsafe(32)
    generated = {
        "POSTGRES_PASSWORD": password,
        "JWT_SECRET_KEY": secret,
        "DATABASE_URL": database_url_with_password(
            entries["DATABASE_URL"],
            entries["POSTGRES_USER"],
            entries["POSTGRES_DB"],
            password,
        ),
    }
    output = []
    for line in lines:
        key = line.partition("=")[0]
        output.append(f"{key}={generated[key]}" if key in generated else line)
    validate_existing(read_entries(output))
    with target.open("x", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(output) + "\n")
    return True


def main() -> None:
    root = Path.cwd()
    try:
        created = create_env(root / ".env.example", root / ".env")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Could not prepare .env: {exc}") from exc
    print("Created .env" if created else "Existing .env is valid; left unchanged")


if __name__ == "__main__":
    main()
