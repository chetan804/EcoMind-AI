"""Application settings, loaded from environment variables and validated at startup.

All deployment-specific values (database URL, CORS origins, storage, auth, model artifact
path) come from the environment. Nothing here is read by the browser bundle.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32
_PLACEHOLDER_MARKERS = ("change_me", "changeme", "replace-with", "replace_with")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = False

    # Required: there is deliberately no default, so a missing value fails at startup.
    database_url: str
    secret_key: SecretStr

    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_expire_days: int = Field(default=14, ge=1, le=90)
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    file_storage_backend: Literal["local"] = "local"
    file_storage_local_path: Path = Path("./var/storage")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    model_artifacts_dir: Path = Path("../ml/artifacts")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _require_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://...)")
        return value

    @model_validator(mode="after")
    def _validate_environment_rules(self) -> Self:
        secret = self.secret_key.get_secret_value()
        if len(secret) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters")
        if self.environment != "test" and any(m in secret.lower() for m in _PLACEHOLDER_MARKERS):
            raise ValueError("SECRET_KEY still contains the example placeholder; generate a value")
        if self.environment == "production":
            if "*" in self.cors_allowed_origins:
                raise ValueError("CORS_ALLOWED_ORIGINS must not contain '*' in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings. Raises pydantic.ValidationError if misconfigured."""
    return Settings()  # required fields come from the environment
