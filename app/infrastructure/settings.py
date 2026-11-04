from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_access_minutes: int = Field(default=15, gt=0)
    jwt_refresh_days: int = Field(default=7, gt=0)

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_example_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().startswith("replace-with-"):
            raise ValueError("JWT_SECRET_KEY must be replaced with a random secret")
        return value


settings = Settings.model_validate({})
