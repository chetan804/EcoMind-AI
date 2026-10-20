#!/usr/bin/env python3
"""Verify the repository matches the canonical structure (docs/architecture/component-boundaries.md).

Checks that every canonical directory/file exists, that no unexpected top-level entry (for
example a second application root) has been added, and that every backend module and frontend
feature directory is documented. Changing the canonical layout requires an ADR and an update
to the lists below.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BACKEND_MODULES = [
    "auth", "users", "waste_reports", "classification", "collection", "route_planning",
    "facilities", "fleet", "circular_economy", "analytics", "forecasting", "anomaly_detection",
    "community_incidents", "sorting_guide", "material_passports", "rewards", "notifications",
    "audit", "administration",
]  # fmt: skip
FRONTEND_FEATURES = [
    "auth", "dashboard", "waste-classification", "waste-reports", "collection", "route-planning",
    "facilities", "fleet", "circular-economy", "analytics", "forecasting", "anomaly-alerts",
    "community-incidents", "sorting-guide", "material-passports", "rewards", "notifications",
    "users", "audit", "settings",
    "landing",  # public marketing page: not a backend domain, added by the UI milestone (docs/ui/design-system.md)
]  # fmt: skip
INTEGRATIONS = ["file_storage", "mapping", "email", "sensors"]
ML_CAPABILITIES = ["waste_classification", "forecasting", "anomaly_detection"]

REQUIRED_DIRS = [
    "frontend/public", "frontend/src/app/guards", "frontend/src/assets",
    *(f"frontend/src/components/{d}" for d in ("ui", "layout", "data-display", "forms", "feedback", "navigation")),
    *(f"frontend/src/features/{f}" for f in FRONTEND_FEATURES),
    "frontend/src/hooks", "frontend/src/lib", "frontend/src/services", "frontend/src/types",
    "frontend/src/utils", "frontend/src/styles",
    "frontend/tests/unit", "frontend/tests/components", "frontend/tests/integration",
    "backend/app/api/v1", "backend/app/core", "backend/app/db", "backend/app/common",
    *(f"backend/app/modules/{m}" for m in BACKEND_MODULES),
    *(f"backend/app/integrations/{i}" for i in INTEGRATIONS),
    "backend/app/health", "backend/migrations/versions",
    *(f"backend/tests/{d}" for d in ("unit", "integration", "api", "security", "fixtures")),
    "ml/common/config", "ml/common/preprocessing", "ml/common/evaluation", "ml/model_registry",
    "ml/artifacts", "ml/configs", "ml/notebooks",
    *(f"ml/{c}/{d}" for c in ML_CAPABILITIES for d in ("data", "training", "evaluation", "inference")),
    "ml/waste_classification/experiments",
    *(f"datasets/{d}" for d in ("raw", "interim", "processed", "external", "manifests")),
    "deployment/docker", "deployment/scripts",
    "tests/e2e", "tests/contract", "tests/smoke",
    *(f"scripts/{d}" for d in ("setup", "development", "database", "ml", "quality")),
    *(f"docs/{d}" for d in ("architecture", "decisions", "requirements", "api", "database", "ml/model-cards",
                            "security", "testing", "ui", "operations")),
    ".github/workflows",
]  # fmt: skip

REQUIRED_FILES = [
    "frontend/src/app/App.tsx", "frontend/src/app/router.tsx", "frontend/src/app/providers.tsx",
    "frontend/src/app/query-client.ts", "frontend/src/app/config.ts",
    "frontend/src/services/api-client.ts", "frontend/src/services/error-handler.ts",
    "frontend/src/main.tsx", "frontend/src/vite-env.d.ts",
    "frontend/.env.example", "frontend/package.json", "frontend/tsconfig.json",
    "frontend/vite.config.ts", "frontend/eslint.config.js", "frontend/README.md",
    "backend/app/main.py", "backend/app/api/router.py", "backend/app/api/v1/router.py",
    *(f"backend/app/core/{f}.py" for f in ("config", "security", "logging", "exceptions", "middleware", "permissions")),
    *(f"backend/app/db/{f}.py" for f in ("base", "session", "metadata")),
    *(f"backend/app/common/{f}.py" for f in ("pagination", "enums", "response_schemas", "time")),
    "backend/migrations/env.py", "backend/alembic.ini", "backend/pyproject.toml",
    "backend/.env.example", "backend/README.md",
    "ml/README.md", "ml/artifacts/.gitkeep",
    *(f"ml/{c}/README.md" for c in ML_CAPABILITIES),
    "datasets/README.md",
    "deployment/docker/frontend.Dockerfile", "deployment/docker/backend.Dockerfile", "deployment/README.md",
    "tests/README.md", "scripts/README.md",
    *(f"docs/architecture/{f}.md" for f in ("system-overview", "component-boundaries", "data-flow", "deployment-architecture")),
    "docs/decisions/ADR-0001-modular-monolith.md",
    *(f"docs/requirements/{f}.md" for f in ("project-scope", "functional-requirements", "non-functional-requirements")),
    "docs/api/api-conventions.md", "docs/database/schema-overview.md", "docs/database/data-dictionary.md",
    "docs/ml/evaluation-protocol.md", "docs/security/security-baseline.md",
    "docs/testing/testing-strategy.md", "docs/ui/design-system.md", "docs/ui/screen-inventory.md",
    "docs/operations/runbook.md", "docs/operations/troubleshooting.md", "docs/project-roadmap.md",
    *(f".github/workflows/{f}.yml" for f in ("backend-ci", "frontend-ci", "quality-gates")),
    ".gitignore", ".dockerignore", ".editorconfig", ".gitattributes", ".env.example",
    "compose.yaml", "Makefile", "README.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE",
]  # fmt: skip

# Everything allowed at the repository root (hidden tooling folders such as .git are ignored).
ALLOWED_TOP_LEVEL = {
    "frontend", "backend", "ml", "datasets", "deployment", "tests", "scripts", "docs",
    ".github", ".gitignore", ".dockerignore", ".editorconfig", ".gitattributes", ".env",
    ".env.example", "compose.yaml", "Makefile", "README.md", "CONTRIBUTING.md", "SECURITY.md",
    "LICENSE", ".git",
    # tool caches (git-ignored)
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}  # fmt: skip


REFERENCE_DIR = "docs/ui/reference"


def reference_problems() -> list[str]:
    """The design references are immutable originals: each must exist and match its recorded SHA-256."""
    manifest_path = ROOT / REFERENCE_DIR / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing file: {REFERENCE_DIR}/manifest.json"]
    problems: list[str] = []
    for screen in json.loads(manifest_path.read_text(encoding="utf-8"))["screens"]:
        image = ROOT / REFERENCE_DIR / screen["filename"]
        if not image.is_file():
            problems.append(f"missing reference image: {REFERENCE_DIR}/{screen['filename']}")
        elif hashlib.sha256(image.read_bytes()).hexdigest() != screen["sha256"]:
            problems.append(f"reference image was modified (sha256 differs from manifest): {screen['filename']}")
    return problems


def main() -> int:
    problems: list[str] = []
    problems += [f"missing directory: {d}" for d in REQUIRED_DIRS if not (ROOT / d).is_dir()]
    problems += [f"missing file: {f}" for f in REQUIRED_FILES if not (ROOT / f).is_file()]
    problems += reference_problems()
    for entry in sorted(ROOT.iterdir()):
        if entry.name not in ALLOWED_TOP_LEVEL:
            problems.append(f"unexpected top-level entry: {entry.name} (see docs/decisions)")
    for module in BACKEND_MODULES:
        if not (ROOT / "backend/app/modules" / module / "README.md").is_file():
            problems.append(f"backend module without README.md: {module}")
    for feature in FRONTEND_FEATURES:
        if not (ROOT / "frontend/src/features" / feature / "README.md").is_file():
            problems.append(f"frontend feature without README.md: {feature}")
    for integration in INTEGRATIONS:
        if not (ROOT / "backend/app/integrations" / integration / "README.md").is_file():
            problems.append(f"integration without README.md: {integration}")
    for problem in problems:
        print(f"ERROR {problem}")
    if not problems:
        print(f"structure ok ({len(REQUIRED_DIRS)} directories, {len(REQUIRED_FILES)} files checked)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
