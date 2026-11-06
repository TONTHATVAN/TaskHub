from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

import jwt

from app.core.constants import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER


class InvalidTokenError(Exception):
    pass


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    token_id: UUID | None
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class JwtTokenService:
    def __init__(self, secret_key: str, access_minutes: int, refresh_days: int) -> None:
        self._secret_key = secret_key
        self._access_minutes = access_minutes
        self._refresh_days = refresh_days

    def issue_access(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        return self._encode(
            user_id,
            TokenType.ACCESS,
            now,
            now + timedelta(minutes=self._access_minutes),
        )

    def issue_refresh(self, user_id: UUID) -> tuple[str, UUID, datetime]:
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=self._refresh_days)
        token_id = uuid4()
        token = self._encode(user_id, TokenType.REFRESH, now, expires_at, token_id)
        return token, token_id, expires_at

    def decode(self, token: str, expected_type: TokenType) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
            )
            if payload["type"] != expected_type:
                raise InvalidTokenError
            user_id = UUID(payload["sub"])
            token_id = (
                UUID(payload["jti"]) if expected_type is TokenType.REFRESH else None
            )
            expires_at = datetime.fromtimestamp(payload["exp"], UTC)
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError from exc
        return TokenClaims(user_id=user_id, token_id=token_id, expires_at=expires_at)

    def _encode(
        self,
        user_id: UUID,
        token_type: TokenType,
        issued_at: datetime,
        expires_at: datetime,
        token_id: UUID | None = None,
    ) -> str:
        payload = {
            "sub": str(user_id),
            "type": token_type,
            "iat": issued_at,
            "exp": expires_at,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        }
        if token_id is not None:
            payload["jti"] = str(token_id)
        return jwt.encode(payload, self._secret_key, algorithm=JWT_ALGORITHM)
