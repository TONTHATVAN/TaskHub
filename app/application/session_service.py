from datetime import UTC, datetime
from uuid import UUID

from app.application.passwords import verify_password
from app.application.tokens import InvalidTokenError, JwtTokenService, TokenPair
from app.domain.refresh_token_repository import RefreshTokenRepository
from app.domain.user_repository import UserRepository


class InvalidCredentialsError(Exception):
    pass


class SessionService:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: JwtTokenService,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self._users.get_by_email(email)
        if (
            user is None
            or not user.is_active
            or not await verify_password(password, user.hashed_password)
        ):
            raise InvalidCredentialsError
        return await self._issue_pair(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode(refresh_token, "refresh")
        if claims.token_id is None:
            raise InvalidTokenError
        user = await self._users.get_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError
        if not await self._refresh_tokens.consume(
            claims.token_id, user.id, datetime.now(UTC)
        ):
            raise InvalidTokenError
        return await self._issue_pair(user.id)

    async def logout(self, refresh_token: str) -> None:
        claims = self._tokens.decode(refresh_token, "refresh")
        if claims.token_id is None:
            raise InvalidTokenError
        if not await self._refresh_tokens.consume(
            claims.token_id, claims.user_id, datetime.now(UTC)
        ):
            raise InvalidTokenError

    async def _issue_pair(self, user_id: UUID) -> TokenPair:
        access_token = self._tokens.issue_access(user_id)
        refresh_token, token_id, expires_at = self._tokens.issue_refresh(user_id)
        await self._refresh_tokens.add(token_id, user_id, expires_at)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)
