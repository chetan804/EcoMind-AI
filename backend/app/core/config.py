"""Application configuration.

All secrets come from the environment or a local `.env` file. A random secret
key is generated for development if none is provided; production refuses to
boot without an explicit key.
"""

from __future__ import annotations

import secrets
import warnings
from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="ECOMIND_",
        extra="ignore",
    )

    # Core
    environment: str = "development"  # development | test | staging | production
    api_prefix: str = "/api/v1"
    project_name: str = "EcoMind-AI"
    log_level: str = "INFO"

    # Security
    secret_key: str = ""  # must be set explicitly in production
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    password_reset_minutes: int = 60
    # Argon2id via argon2-cffi defaults (memory 64 MiB, t=3, p=4) is a modern,
    # memory-hard baseline; tune via env if hardware requires it.
    cors_origins: str = "*"  # comma-separated

    # Database — Unix-socket URL to the bundled dev PostgreSQL by default.
    database_url: str = "postgresql+asyncpg://postgres@/ecomind?host=/home/user/EcoMind-AI/.pgdata"

    # Storage
    data_dir: Path = BASE_DIR / "data"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB
    allowed_upload_mimes: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    # AI providers. No key is required: the platform falls back to a clearly
    # labelled deterministic baseline and flags items for human review.
    ai_default_provider: str = "heuristic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com"
    google_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ai_request_timeout_seconds: float = 45.0
    ai_max_image_bytes: int = 8 * 1024 * 1024

    # Routing / optimisation
    osrm_base_url: str = ""  # empty -> estimated-geometry fallback (clearly labelled)
    road_distance_factor: float = 1.3  # haversine * factor when OSRM unavailable
    route_sync_max_stops: int = 40  # optimise inline below this, else queue a job

    # Background jobs
    run_embedded_worker: bool = True
    worker_poll_seconds: float = 1.0

    # Demo / simulation
    enable_demo_simulator: bool = False
    demo_simulator_interval_seconds: int = 30

    # Rate limits (requests per minute) by category
    rate_limit_auth: int = 15
    rate_limit_write: int = 60
    rate_limit_ai: int = 20
    rate_limit_upload: int = 30
    rate_limit_telemetry: int = 600
    rate_limit_read: int = 600

    @field_validator("database_url")
    @classmethod
    def _normalise_dsn(cls, v: str) -> str:
        # Accept bare postgres:// and keep asyncpg driver canonical.
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    def effective_secret_key(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.is_production:
            raise RuntimeError(
                "ECOMIND_SECRET_KEY must be set to a high-entropy random value in production."
            )
        warnings.warn(
            "ECOMIND_SECRET_KEY not set — generated an ephemeral key. "
            "Tokens will not survive restarts. Set it in backend/.env for stable development.",
            stacklevel=2,
        )
        return secrets.token_urlsafe(48)

    def sqlalchemy_echo(self) -> bool:
        return self.log_level == "SQL"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
