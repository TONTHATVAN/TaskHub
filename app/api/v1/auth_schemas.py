from datetime import datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import (
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    USER_EMAIL_MAX_LENGTH,
    USER_FULL_NAME_MAX_LENGTH,
    USER_FULL_NAME_MIN_LENGTH,
)
from app.core.messages import (
    FULL_NAME_EMPTY_MESSAGE,
    NULL_REQUIRED_FIELD_MESSAGE,
    PASSWORD_TOO_LONG_MESSAGE,
)
from app.domain.user import UserRole
from app.domain.user_repository import UserProfileChanges


def validate_password_bytes(value: object) -> object:
    if not isinstance(value, str):
        return value
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_TOO_LONG_MESSAGE)
    return value


def normalize_full_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        raise ValueError(FULL_NAME_EMPTY_MESSAGE)
    return value


class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=USER_EMAIL_MAX_LENGTH)
    full_name: str = Field(
        min_length=USER_FULL_NAME_MIN_LENGTH, max_length=USER_FULL_NAME_MAX_LENGTH
    )
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_BYTES)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        return normalize_full_name(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_length(cls, value: object) -> object:
        return validate_password_bytes(value)


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    email: EmailStr | None = Field(default=None, max_length=USER_EMAIL_MAX_LENGTH)
    full_name: str | None = Field(
        default=None,
        min_length=USER_FULL_NAME_MIN_LENGTH,
        max_length=USER_FULL_NAME_MAX_LENGTH,
    )

    @field_validator("email", mode="before")
    @classmethod
    def reject_null_email(cls, value: object) -> object:
        if value is None:
            raise ValueError(NULL_REQUIRED_FIELD_MESSAGE)
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        if value is None:
            raise ValueError(NULL_REQUIRED_FIELD_MESSAGE)
        return normalize_full_name(value)

    def to_changes(self) -> UserProfileChanges:
        return cast(UserProfileChanges, self.model_dump(exclude_unset=True))


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=PASSWORD_MAX_BYTES)
    new_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_BYTES
    )

    @field_validator("current_password", "new_password", mode="before")
    @classmethod
    def validate_password_length(cls, value: object) -> object:
        return validate_password_bytes(value)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=USER_EMAIL_MAX_LENGTH)
    password: str = Field(max_length=PASSWORD_MAX_BYTES)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_length(cls, value: object) -> object:
        return validate_password_bytes(value)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPairRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
