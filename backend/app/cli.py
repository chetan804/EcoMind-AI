"""Operator commands. Run from the backend directory, with the same environment as the API.

    python -m app.cli create-admin --email admin@example.org --name "Site Admin"

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

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.modules.audit import service as audit
from app.modules.auth.errors import EmailAlreadyRegisteredError, WeakPasswordError
from app.modules.auth.policy import password_problems
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="create an administrator account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True, help="full name")
    args = parser.parse_args(argv)

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
