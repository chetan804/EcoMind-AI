"""Operator commands. Run from the backend directory, with the same environment as the API.

    python -m app.cli create-admin --email admin@example.org --name "Site Admin"
    python -m app.cli register-model --version 1.0.0     # verify + register a trained artifact
    python -m app.cli activate-model --version 1.0.0     # make it the model that answers
    python -m app.cli import-reference-series --key austin   # public series for forecasting demos
    python -m app.cli purge-location-events                  # retention: run daily (cron/timer)
    python -m app.cli expire-marketplace-listings            # close lapsed marketplace listings
    python -m app.cli purge-account-tokens                   # delete expired reset/verify links
    python -m app.cli seed-support-knowledge                 # load the shipped help articles
    python -m app.cli purge-assistant-conversations          # retention: run daily (cron/timer)
    python -m app.cli mark-email-verified --email a@b.org    # operator attests an address
    python -m app.cli mark-email-verified --all-existing     # before EMAIL_VERIFICATION_REQUIRED

The password is read from the ECOMIND_ADMIN_PASSWORD environment variable or, when that is unset,
prompted for without echo. It is never accepted as a command-line argument (it would leak into
shell history and process listings). The account gets the ``administrator`` role and is subject to
the normal password policy.
"""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys

from sqlalchemy import select

from app.common.time import utc_now
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth import recovery
from app.modules.auth.errors import EmailAlreadyRegisteredError, WeakPasswordError
from app.modules.auth.policy import password_problems
from app.modules.classification import repository as classification_repository
from app.modules.classification import service as classification_service
from app.modules.forecasting import importer as forecasting_importer
from app.modules.marketplace import expiry as marketplace_expiry
from app.modules.support import assistant as support_assistant
from app.modules.support import knowledge as support_knowledge
from app.modules.tracking import service as tracking_service
from app.modules.users import repository as users
from app.modules.users.models import User

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
        user.email_verified_at = utc_now()  # created by an operator with shell access
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


def import_reference(*, key: str) -> str:
    with get_session_factory()() as db:
        row = forecasting_importer.import_reference_series(db, key, context=RequestContext())
        return (
            f"reference series {row.key}: {row.point_count} weeks, "
            f"{row.first_period} to {row.last_period}"
        )


def purge_location_events() -> str:
    settings = get_settings()
    with get_session_factory()() as db:
        removed = tracking_service.purge_expired(db, settings)
    return (
        f"removed {removed} vehicle location events older than "
        f"{settings.tracking_retention_days} days"
    )


def purge_account_tokens() -> str:
    with get_session_factory()() as db:
        removed = recovery.purge_expired_tokens(db)
    return f"removed {removed} expired or used account tokens"


def expire_marketplace_listings() -> str:
    with get_session_factory()() as db:
        result = marketplace_expiry.run(db)
    return f"closed {result.closed} expired listing(s); warned owners of {result.announced}"


def seed_support_knowledge() -> str:
    with get_session_factory()() as db:
        created, updated = support_knowledge.seed_platform_help(db)
    return f"help articles: {created} created, {updated} updated (edited articles are left alone)"


def purge_assistant_conversations() -> str:
    settings = get_settings()
    with get_session_factory()() as db:
        removed = support_assistant.purge_old_conversations(
            db, older_than_days=settings.assistant_retention_days
        )
    return (
        f"removed {removed} assistant conversation(s) idle for more than "
        f"{settings.assistant_retention_days} days (conversations shared with a ticket are kept)"
    )


def mark_email_verified(*, email: str | None, all_existing: bool) -> str:
    """An operator attests that addresses are genuine (audited). Never done implicitly."""
    with get_session_factory()() as db:
        if all_existing:
            targets = list(db.scalars(select(User).where(User.email_verified_at.is_(None))))
        else:
            found = users.get_by_email(db, email or "")
            if found is None:
                raise AppError(f"No account with e-mail {email}")
            targets = [found] if found.email_verified_at is None else []
        now = utc_now()
        for user in targets:
            user.email_verified_at = now
            audit.record(
                db,
                action="auth.email_verified_by_operator",
                entity_type="user",
                entity_id=user.id,
                context=RequestContext(),
            )
        db.commit()
    return f"marked {len(targets)} account(s) as e-mail verified"


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
    reference = sub.add_parser(
        "import-reference-series", help="import a public series (with provenance) for demos"
    )
    reference.add_argument("--key", required=True)
    sub.add_parser(
        "purge-location-events",
        help="delete vehicle location events older than TRACKING_RETENTION_DAYS",
    )
    sub.add_parser(
        "expire-marketplace-listings",
        help="close marketplace listings past their expiry and warn owners of those about to lapse",
    )
    sub.add_parser("purge-account-tokens", help="delete expired or used reset/verification links")
    sub.add_parser(
        "seed-support-knowledge", help="create or refresh the help articles that ship with the app"
    )
    sub.add_parser(
        "purge-assistant-conversations",
        help="delete assistant conversations idle for more than ASSISTANT_RETENTION_DAYS",
    )
    verify = sub.add_parser("mark-email-verified", help="attest e-mail addresses as verified")
    target = verify.add_mutually_exclusive_group(required=True)
    target.add_argument("--email")
    target.add_argument("--all-existing", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "expire-marketplace-listings":
        print(expire_marketplace_listings())
        return 0

    if args.command == "seed-support-knowledge":
        print(seed_support_knowledge())
        return 0

    if args.command == "purge-assistant-conversations":
        print(purge_assistant_conversations())
        return 0

    if args.command == "purge-account-tokens":
        print(purge_account_tokens())
        return 0

    if args.command == "mark-email-verified":
        try:
            print(mark_email_verified(email=args.email, all_existing=args.all_existing))
        except AppError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        return 0

    if args.command == "purge-location-events":
        print(purge_location_events())
        return 0

    if args.command == "import-reference-series":
        try:
            print(import_reference(key=args.key))
        except AppError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        except (RuntimeError, OSError, ImportError, subprocess.CalledProcessError) as exc:
            # The public series are read from a pinned, git-ignored clone that exists only in a
            # development checkout (not in the backend image); say so instead of a traceback.
            print(
                "error: the public reference series could not be read "
                f"({type(exc).__name__}). Run this from a development checkout after "
                "`git clone https://github.com/UCloudMl/solid-waste-prediction "
                "datasets/external/msw-src` and `git -C datasets/external/msw-src checkout "
                "6ff6b1a073e7acbe7725150119a74c5f2fba26d2` (details: "
                "docs/ml/dataset-research/ingestion/INGESTION_REPORT.md).",
                file=sys.stderr,
            )
            return 1
        return 0

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
