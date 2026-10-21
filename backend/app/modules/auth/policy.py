"""Password policy and brute-force limits.

Password rules (checked server-side; the frontend mirrors them for early feedback only):
- 12 to 128 characters (length is the main strength factor; no composition rules).
- Must not contain the user's email local part or be built from the account name.
- Must not be in the small embedded list of the most common passwords below. This is a
  *basic* denylist, not a breached-password corpus; integrating a breach-corpus check is a
  documented follow-up.

Brute-force limits are enforced from the append-only audit log (``audit_logs``) so they are shared
across worker processes without Redis. See ``service.py``.
"""

from __future__ import annotations

from datetime import timedelta

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILED_LOGINS_PER_EMAIL = 5
MAX_FAILED_LOGINS_PER_IP = 30
REGISTER_WINDOW = timedelta(hours=1)
MAX_REGISTRATIONS_PER_IP = 10

# Account e-mails (password reset, address verification). A per-address cap that is exceeded sends
# nothing but still answers 202 (so the endpoint never reveals whether an address has an account);
# the per-IP cap answers 429. Rejected one-time links are capped per IP so tokens cannot be guessed.
ACCOUNT_EMAIL_WINDOW = timedelta(hours=1)
MAX_ACCOUNT_EMAILS_PER_ADDRESS = 3
MAX_ACCOUNT_EMAIL_REQUESTS_PER_IP = 10
TOKEN_REJECT_WINDOW = timedelta(minutes=15)
MAX_TOKEN_REJECTIONS_PER_IP = 20

# A rotated refresh token replayed within this many seconds is treated as a benign race (two tabs
# refreshing at once): the request is refused but the session family is NOT revoked. Replays after
# the grace window are treated as theft and revoke the whole family.
REFRESH_REUSE_GRACE_SECONDS = 10

_COMMON_PASSWORDS = frozenset(
    {
        "password1234", "password12345", "123456789012", "1234567890123", "qwertyuiop12",
        "qwertyuiop123", "iloveyou1234", "letmein12345", "welcome12345", "administrator",
        "passwordpassword", "password123456", "changeme1234", "ecomindai1234", "ecomind12345",
        "123123123123", "111111111111", "000000000000", "abcdefghijkl", "abcd12345678",
        "1q2w3e4r5t6y", "qazwsxedcrfv", "monkey123456", "dragon123456", "football1234",
        "sunshine1234", "princess1234", "trustno12345", "superman1234", "baseball1234",
    }
)  # fmt: skip


def password_problems(password: str, *, email: str, full_name: str) -> list[str]:
    """Return human-readable reasons the password is unacceptable (empty list = acceptable)."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"Use at most {MAX_PASSWORD_LENGTH} characters.")
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS or len(set(lowered)) <= 2:
        problems.append("This password is too common or too repetitive.")
    local_part = email.strip().lower().split("@", 1)[0]
    if len(local_part) >= 4 and local_part in lowered:
        problems.append("Do not include your email address in the password.")
    name_compact = "".join(full_name.lower().split())
    if len(name_compact) >= 6 and name_compact in "".join(lowered.split()):
        problems.append("Do not include your name in the password.")
    return problems
