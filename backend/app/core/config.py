import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: Final[str] = os.getenv("DATABASE_URL", "")
SECRET_KEY: Final[str] = os.getenv("SECRET_KEY", "")
JWT_ALGORITHM: Final[str] = os.getenv("JWT_ALGORITHM", "HS256")
ENVIRONMENT: Final[str] = os.getenv("ENVIRONMENT", "development").lower()
APP_VERSION: Final[str] = os.getenv("APP_VERSION", "1.0.0")
AI_PROVIDER: Final[str] = os.getenv("AI_PROVIDER", "fallback")
AI_MODEL: Final[str] = os.getenv("AI_MODEL", "configured-locally")
ROUTING_PROVIDER: Final[str] = os.getenv("ROUTING_PROVIDER", "fallback")
OSRM_BASE_URL: Final[str] = os.getenv("OSRM_BASE_URL", "http://127.0.0.1:5000")
OLLAMA_BASE_URL: Final[str] = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
)
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)
RATE_LIMIT_REQUESTS: Final[int] = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
RATE_LIMIT_WINDOW_SECONDS: Final[int] = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
CORS_ORIGINS: Final[list[str]] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not configured")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not configured")

if ENVIRONMENT == "production" and (
    SECRET_KEY in {"change-me-to-a-long-random-secret", "replace-with-a-long-random-secret"}
    or len(SECRET_KEY) < 32
):
    raise ValueError("Production SECRET_KEY must be a unique value of at least 32 characters")

if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

if RATE_LIMIT_REQUESTS <= 0 or RATE_LIMIT_WINDOW_SECONDS <= 0:
    raise ValueError("Rate-limit settings must be positive")