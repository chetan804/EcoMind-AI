"""Application settings, loaded from environment variables and validated at startup.

All deployment-specific values (database URL, CORS origins, storage, auth, model artifact
path) come from the environment. Nothing here is read by the browser bundle.
"""

from __future__ import annotations

from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

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

    # Optional road routing (the default is none: straight-line fallback, labelled as such).
    # ROUTING_PROVIDER=none|google|osrm. Unset keeps the earlier behaviour: google when a server
    # key is set, otherwise none. osrm calls an OSRM server YOU run (OSRM_BASE_URL); it is the
    # only external service the platform can use besides Google and is off unless chosen.
    routing_provider: Literal["none", "google", "osrm"] | None = None
    osrm_base_url: str | None = None
    osrm_timeout_seconds: float = Field(default=8.0, gt=0, le=30)

    # Outbound e-mail (password reset, e-mail verification, security notices).
    # EMAIL_BACKEND=none|console|smtp|memory. Unset resolves to: none in production (nothing is
    # sent, and the API reports that honestly), console in local (messages are written to the log:
    # development only) and memory in tests. console and memory are refused in production.
    email_backend: Literal["none", "console", "smtp", "memory"] | None = None
    email_from: str | None = None
    # Public address of the web app: links in e-mails point here (https required in production).
    app_base_url: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    password_reset_token_minutes: int = Field(default=30, ge=5, le=120)
    email_verification_token_hours: int = Field(default=24, ge=1, le=168)
    # When true, sign-in is refused until the address is verified. Needs working e-mail delivery.
    email_verification_required: bool = False

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

    @field_validator("google_maps_server_api_key", "smtp_password", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "email_backend",
        "email_from",
        "smtp_host",
        "smtp_username",
        mode="before",
    )
    @classmethod
    def _blank_mail_setting_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("email_from")
    @classmethod
    def _email_from_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        address = parseaddr(value)[1]
        if "\n" in value or "\r" in value or "@" not in address:
            raise ValueError("EMAIL_FROM must be an address such as no-reply@example.org")
        return value

    @field_validator("app_base_url")
    @classmethod
    def _app_base_url_shape(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("APP_BASE_URL must be an http(s) URL such as https://app.example.org")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("APP_BASE_URL must not contain credentials, a query or a fragment")
        return value.strip().rstrip("/")

    @field_validator("routing_provider", "osrm_base_url", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("osrm_base_url")
    @classmethod
    def _osrm_url_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("OSRM_BASE_URL must be an http(s) URL such as http://osrm:5000")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("OSRM_BASE_URL must not contain credentials, a query or a fragment")
        return value.rstrip("/")

    @property
    def effective_email_backend(self) -> Literal["none", "console", "smtp", "memory"]:
        """The e-mail backend in force (see the ``email_backend`` comment for the defaults)."""
        if self.email_backend is not None:
            return self.email_backend
        if self.environment == "production":
            return "none"
        return "memory" if self.environment == "test" else "console"

    @property
    def email_enabled(self) -> bool:
        """True when messages can actually be delivered (so reset/verification links are usable)."""
        return self.effective_email_backend != "none"

    @property
    def effective_routing_provider(self) -> Literal["none", "google", "osrm"]:
        """The routing provider in force (the legacy key-only configuration still means google)."""
        if self.routing_provider is not None:
            return self.routing_provider
        return "google" if self.google_maps_server_api_key is not None else "none"

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
        backend = self.effective_email_backend
        if self.environment == "production" and backend in ("console", "memory"):
            raise ValueError(f"EMAIL_BACKEND={backend} is not allowed in production")
        if backend == "memory" and self.environment != "test":
            raise ValueError("EMAIL_BACKEND=memory is only for tests")
        if backend == "smtp":
            if self.smtp_host is None or self.email_from is None:
                raise ValueError("EMAIL_BACKEND=smtp requires SMTP_HOST and EMAIL_FROM")
            if self.smtp_security == "none" and self.environment == "production":
                raise ValueError("SMTP_SECURITY=none is not allowed in production")
            if (self.smtp_username is None) != (self.smtp_password is None):
                raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be set together")
            if self.environment == "production" and not self.app_base_url.startswith("https://"):
                raise ValueError("APP_BASE_URL must be https in production when e-mail is sent")
        if self.email_verification_required and not self.email_enabled:
            raise ValueError(
                "EMAIL_VERIFICATION_REQUIRED=true needs e-mail delivery (EMAIL_BACKEND); "
                "otherwise nobody could verify an address"
            )
        if self.tracking_stale_after_seconds <= self.tracking_live_within_seconds:
            raise ValueError(
                "TRACKING_STALE_AFTER_SECONDS must exceed TRACKING_LIVE_WITHIN_SECONDS"
            )
        if self.routing_provider == "osrm" and self.osrm_base_url is None:
            raise ValueError("ROUTING_PROVIDER=osrm requires OSRM_BASE_URL")
        if self.routing_provider == "google" and self.google_maps_server_api_key is None:
            raise ValueError("ROUTING_PROVIDER=google requires GOOGLE_MAPS_SERVER_API_KEY")
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
