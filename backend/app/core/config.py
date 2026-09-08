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
OLLAMA_BASE_URL: Final[str] = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
)
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)
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

if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")