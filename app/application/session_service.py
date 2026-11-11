from datetime import UTC, datetime
from uuid import UUID

from app.application.passwords import verify_password
from app.application.tokens import (
    InvalidTokenError,
    JwtTokenService,
    TokenPair,
    TokenType,
)
from app.domain.refresh_token_repository import (
    RefreshConsumeResult,
    RefreshTokenRepository,
)
from app.domain.user_repository import UserRepository


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class ReplayedRefreshTokenError(Exception):
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
        user = await self._users.get_by_email_for_update(email)
        if user is None:
            raise InvalidCredentialsError
        if not await verify_password(password, user.hashed_password):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return await self._issue_pair(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        user_id = await self._consume_refresh_token(refresh_token, require_active=True)
        return await self._issue_pair(user_id)

    async def logout(self, refresh_token: str) -> None:
        await self._consume_refresh_token(refresh_token)

    async def _consume_refresh_token(
        self, refresh_token: str, *, require_active: bool = False
    ) -> UUID:
        claims = self._tokens.decode(refresh_token, TokenType.REFRESH)
        if require_active:
            user = await self._users.get_by_id_for_update(claims.user_id)
            if user is None:
                raise InvalidTokenError
            if not user.is_active:
                raise InactiveUserError
        now = datetime.now(UTC)
        consume_result = await self._refresh_tokens.consume(
            claims.token_id, claims.user_id, now
        )
        if consume_result is RefreshConsumeResult.REPLAYED:
            await self._refresh_tokens.revoke_all(claims.user_id, now)
            raise ReplayedRefreshTokenError
        if consume_result is RefreshConsumeResult.INVALID:
            raise InvalidTokenError
        return claims.user_id

    async def _issue_pair(self, user_id: UUID) -> TokenPair:
        access_token = self._tokens.issue_access(user_id)
        refresh_token, token_id, expires_at = self._tokens.issue_refresh(user_id)
        await self._refresh_tokens.add(token_id, user_id, expires_at)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)
