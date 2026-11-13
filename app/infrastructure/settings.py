from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import JWT_SECRET_KEY_MIN_LENGTH
from app.core.messages import JWT_SECRET_KEY_EXAMPLE_MESSAGE


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: SecretStr = Field(min_length=JWT_SECRET_KEY_MIN_LENGTH)
    jwt_access_minutes: int = Field(default=15, gt=0)
    jwt_refresh_days: int = Field(default=7, gt=0)

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_example_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().startswith("replace-with-"):
            raise ValueError(JWT_SECRET_KEY_EXAMPLE_MESSAGE)
        return value


settings = Settings.model_validate({})
