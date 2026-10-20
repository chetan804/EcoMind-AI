#!/usr/bin/env python3
"""Fail if an .env.example file contains something that looks like a real secret.

Rule: variables whose name suggests a secret must be empty or contain an obvious placeholder
(CHANGE_ME...). Also fails if any real .env file is tracked by Git.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECRET_NAME = re.compile(r"(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY|CREDENTIAL)", re.IGNORECASE)
NON_SECRET_VALUE = re.compile(r"^(\d+|true|false)$", re.IGNORECASE)
PLACEHOLDER = re.compile(r"change_?me|replace|your[-_]|example", re.IGNORECASE)
URL_WITH_PASSWORD = re.compile(r"://[^:/\s]+:([^@\s]+)@")


def main() -> int:
    problems: list[str] = []
    for path in sorted(ROOT.glob("**/.env.example")):
        if "node_modules" in path.parts or ".venv" in path.parts:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            location = f"{path.relative_to(ROOT)}:{number}"
            if (
                SECRET_NAME.search(name)
                and value.strip()
                and not NON_SECRET_VALUE.match(value.strip())
                and not PLACEHOLDER.search(value)
            ):
                problems.append(f"{location}: {name} has a non-placeholder value")
            match = URL_WITH_PASSWORD.search(value)
            if match and not PLACEHOLDER.search(match.group(1)):
                problems.append(f"{location}: {name} embeds a real-looking password")
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for name in tracked:
        base = Path(name).name
        if base.startswith(".env") and base != ".env.example":
            problems.append(f"{name}: environment file must not be tracked")
    for problem in problems:
        print(f"ERROR {problem}")
    if not problems:
        print("env templates ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
