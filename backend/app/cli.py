"""Operator commands. Run from the backend directory, with the same environment as the API.

    python -m app.cli create-admin --email admin@example.org --name "Site Admin"
    python -m app.cli register-model --version 1.0.0     # verify + register a trained artifact
    python -m app.cli activate-model --version 1.0.0     # make it the model that answers

The password is read from the ECOMIND_ADMIN_PASSWORD environment variable or, when that is unset,
prompted for without echo. It is never accepted as a command-line argument (it would leak into
shell history and process listings). The account gets the ``administrator`` role and is subject to
the normal password policy.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.errors import EmailAlreadyRegisteredError, WeakPasswordError
from app.modules.auth.policy import password_problems
from app.modules.classification import repository as classification_repository
from app.modules.classification import service as classification_service
from app.modules.users import repository as users

ADMIN_ROLE = "administrator"


def create_admin(*, email: str, full_name: str, password: str) -> None:
    problems = password_problems(password, email=email, full_name=full_name)
    if problems:
        raise WeakPasswordError("Password does not meet the password policy: " + " ".join(problems))
    with get_session_factory()() as db:
        if users.get_by_email(db, email) is not None:
            raise EmailAlreadyRegisteredError("An account with this email already exists")
        role = users.get_role_by_name(db, ADMIN_ROLE)
        if role is None:
            raise RuntimeError("Role 'administrator' is missing; run `alembic upgrade head` first")
        user = users.add(
            db, email=email, password_hash=hash_password(password), full_name=full_name
        )
        users.assign_role(db, user_id=user.id, role_id=role.id)
        audit.record(
            db,
            action="users.admin_created_by_cli",
            entity_type="user",
            entity_id=user.id,
            changes={"role": ADMIN_ROLE},
        )
        db.commit()


def register_model(*, version: str) -> str:
    """Verify the artifact under MODEL_ARTIFACTS_DIR and register it as a candidate."""
    settings = get_settings()
    with get_session_factory()() as db:
        row = classification_service.register_model(
            db, settings.model_artifacts_dir, version, context=RequestContext()
        )
        return (
            f"{row.name} {row.version} registered ({row.status.value}), "
            f"sha256 {row.artifact_manifest_sha256}"
        )


def activate_model(*, version: str) -> str:
    settings = get_settings()
    with get_session_factory()() as db:
        candidates = [
            v for v in classification_repository.list_versions(db) if v.version == version
        ]
        if len(candidates) != 1:
            raise AppError(f"Expected exactly one registered model with version {version}")
        out = classification_service.activate_model(
            db,
            settings.model_artifacts_dir,
            candidates[0].id,
            actor_id=None,
            context=RequestContext(),
        )
        return f"{out.name} {out.version} is now {out.status.value}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="create an administrator account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True, help="full name")
    for name, help_text in (
        ("register-model", "verify and register a trained classification artifact"),
        ("activate-model", "make a registered classification model version active"),
    ):
        model = sub.add_parser(name, help=help_text)
        model.add_argument("--version", required=True)
    args = parser.parse_args(argv)

    if args.command in ("register-model", "activate-model"):
        action = register_model if args.command == "register-model" else activate_model
        try:
            print(action(version=args.version))
        except AppError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        return 0

    password = os.environ.get("ECOMIND_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        create_admin(email=args.email, full_name=args.name, password=password)
    except (WeakPasswordError, EmailAlreadyRegisteredError) as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    print(f"Administrator {args.email.strip().lower()} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
