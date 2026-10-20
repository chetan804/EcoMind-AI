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

    # Rewards policy: points awarded per verified kilogram collected for a reporter. This is a
    # programme policy parameter chosen by the operator, not a scientific constant.
    reward_points_per_kg: int = Field(default=10, ge=0, le=1000)

    # Google Maps Platform (server side). Optional: without a key, road routes are reported as
    # unavailable and the UI falls back to labelled straight lines. NEVER expose this value to the
    # browser; the browser uses its own, referrer-restricted key (VITE_GOOGLE_MAPS_API_KEY).
    google_maps_server_api_key: SecretStr | None = None
    google_routes_timeout_seconds: float = Field(default=8.0, gt=0, le=30)

    # Vehicle tracking. Thresholds are operational policy, not physical constants.
    tracking_live_within_seconds: int = Field(default=120, ge=10, le=3600)
    tracking_stale_after_seconds: int = Field(default=900, ge=60, le=86400)
    tracking_max_future_skew_seconds: int = Field(default=120, ge=0, le=3600)
    tracking_max_report_age_hours: int = Field(default=6, ge=1, le=168)
    tracking_max_events_per_minute: int = Field(default=30, ge=1, le=600)
    tracking_retention_days: int = Field(default=90, ge=1, le=3650)
    # The simulator writes clearly separated, labelled events. It is off in production unless an
    # operator opts in explicitly (e.g. for a demonstration environment).
    tracking_simulator_enabled: bool | None = None

    @field_validator("google_maps_server_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

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
        if self.tracking_stale_after_seconds <= self.tracking_live_within_seconds:
            raise ValueError(
                "TRACKING_STALE_AFTER_SECONDS must exceed TRACKING_LIVE_WITHIN_SECONDS"
            )
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def simulator_enabled(self) -> bool:
        if self.tracking_simulator_enabled is not None:
            return self.tracking_simulator_enabled
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings. Raises pydantic.ValidationError if misconfigured."""
    return Settings()  # required fields come from the environment
