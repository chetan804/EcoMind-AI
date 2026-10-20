#!/usr/bin/env python3
"""Create .env files from the committed templates and generate local secrets.

Never overwrites an existing file. Run via `make env`.
"""

from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [".env", "backend/.env", "frontend/.env"]


def render(template: str, db_password: str, secret_key: str) -> str:
    lines = []
    for line in template.splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            line = f"POSTGRES_PASSWORD={db_password}"
        elif line.startswith("SECRET_KEY="):
            line = f"SECRET_KEY={secret_key}"
        elif line.startswith("DATABASE_URL="):
            line = f"DATABASE_URL=postgresql+psycopg://ecomind:{db_password}@localhost:5432/ecomind"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    db_password = secrets.token_hex(16)  # hex is URL-safe, so it can sit inside DATABASE_URL
    secret_key = secrets.token_urlsafe(48)
    root_env = ROOT / ".env"
    if root_env.exists():  # keep backend/.env consistent with an existing root .env
        for line in root_env.read_text().splitlines():
            if line.startswith("POSTGRES_PASSWORD="):
                db_password = line.split("=", 1)[1]
            elif line.startswith("SECRET_KEY="):
                secret_key = line.split("=", 1)[1]
    for target in TARGETS:
        destination = ROOT / target
        if destination.exists():
            print(f"kept     {target} (already exists)")
            continue
        template = (ROOT / f"{target}.example").read_text()
        destination.write_text(render(template, db_password, secret_key))
        destination.chmod(0o600)
        print(f"created  {target}")


if __name__ == "__main__":
    main()
