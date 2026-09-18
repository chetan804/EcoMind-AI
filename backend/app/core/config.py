import os
from dataclasses import dataclass
from typing import Final, Mapping

from dotenv import load_dotenv


load_dotenv()
SUPPORTED_ENVIRONMENTS: Final[frozenset[str]] = frozenset({"development", "test", "production"})


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    jwt_algorithm: str
    environment: str
    app_version: str
    ai_provider: str
    ai_model: str
    routing_provider: str
    osrm_base_url: str
    ollama_base_url: str
    access_token_expire_minutes: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    cors_origins: tuple[str, ...]


def _positive_int(environ: Mapping[str, str], name: str, default: str) -> int:
    try:
        value = int(environ.get(name, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if environ is None else environ
    environment = source.get("ENVIRONMENT", "development").lower()
    if environment not in SUPPORTED_ENVIRONMENTS:
        raise ValueError("ENVIRONMENT must be one of: development, test, production")
    database_url = source.get("DATABASE_URL", "")
    secret_key = source.get("SECRET_KEY", "")
    if not database_url:
        raise ValueError("DATABASE_URL is not configured")
    if not secret_key:
        raise ValueError("SECRET_KEY is not configured")
    if environment == "production" and (
        secret_key in {"change-me-to-a-long-random-secret", "replace-with-a-long-random-secret"}
        or len(secret_key) < 32
    ):
        raise ValueError("Production SECRET_KEY must be a unique value of at least 32 characters")
    cors_origins = tuple(
        origin.strip()
        for origin in source.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    )
    if not cors_origins:
        raise ValueError("CORS_ORIGINS must contain at least one origin")
    if environment == "production" and "*" in cors_origins:
        raise ValueError("Production CORS_ORIGINS must not contain '*'")
    return Settings(
        database_url=database_url,
        secret_key=secret_key,
        jwt_algorithm=source.get("JWT_ALGORITHM", "HS256"),
        environment=environment,
        app_version=source.get("APP_VERSION", "1.0.0"),
        ai_provider=source.get("AI_PROVIDER", "fallback"),
        ai_model=source.get("AI_MODEL", "configured-locally"),
        routing_provider=source.get("ROUTING_PROVIDER", "fallback"),
        osrm_base_url=source.get("OSRM_BASE_URL", "http://127.0.0.1:5000"),
        ollama_base_url=source.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        access_token_expire_minutes=_positive_int(source, "ACCESS_TOKEN_EXPIRE_MINUTES", "60"),
        rate_limit_requests=_positive_int(source, "RATE_LIMIT_REQUESTS", "120"),
        rate_limit_window_seconds=_positive_int(source, "RATE_LIMIT_WINDOW_SECONDS", "60"),
        cors_origins=cors_origins,
    )


settings: Final[Settings] = load_settings()
DATABASE_URL: Final[str] = settings.database_url
SECRET_KEY: Final[str] = settings.secret_key
JWT_ALGORITHM: Final[str] = settings.jwt_algorithm
ENVIRONMENT: Final[str] = settings.environment
APP_VERSION: Final[str] = settings.app_version
AI_PROVIDER: Final[str] = settings.ai_provider
AI_MODEL: Final[str] = settings.ai_model
ROUTING_PROVIDER: Final[str] = settings.routing_provider
OSRM_BASE_URL: Final[str] = settings.osrm_base_url
OLLAMA_BASE_URL: Final[str] = settings.ollama_base_url
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = settings.access_token_expire_minutes
RATE_LIMIT_REQUESTS: Final[int] = settings.rate_limit_requests
RATE_LIMIT_WINDOW_SECONDS: Final[int] = settings.rate_limit_window_seconds
CORS_ORIGINS: Final[list[str]] = list(settings.cors_origins)
