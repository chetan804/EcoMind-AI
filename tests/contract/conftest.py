"""Contract tests import the backend app directly (no server, no database needed)."""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://contract:contract@127.0.0.1:1/unused")
os.environ.setdefault("SECRET_KEY", "contract-test-only-secret-key-0123456789")
