"""TOTP/HOTP against the published RFC vectors, plus replay and drift behaviour."""

from __future__ import annotations

import base64

import pytest

from app.core.crypto import (
    DecryptionError,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    keyed_hash,
)
from app.modules.auth import totp

# RFC 4226 appendix D and RFC 6238 appendix B use this ASCII secret.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
KEY_A = "a" * 40
KEY_B = "b" * 40


def test_hotp_matches_rfc_4226_appendix_d() -> None:
    expected = [
        "755224",
        "287082",
        "359152",
        "969429",
        "338314",
        "254676",
        "287922",
        "162583",
        "399871",
        "520489",
    ]
    assert [totp.hotp(RFC_SECRET, i) for i in range(10)] == expected


@pytest.mark.parametrize(
    ("unix_time", "expected"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_totp_matches_rfc_6238_sha1_vectors(unix_time: int, expected: str) -> None:
    assert totp.totp(RFC_SECRET, unix_time, digits=8) == expected


def test_secret_is_160_bits_of_base32_and_unique() -> None:
    first, second = totp.generate_secret(), totp.generate_secret()
    assert first != second
    assert len(first) == 32 and first.isalnum() and first == first.upper()
    assert len(base64.b32decode(first)) == 20


def test_code_accepted_for_current_and_adjacent_steps_only() -> None:
    now = 1_700_000_000.0
    for offset, ok in ((-2, False), (-1, True), (0, True), (1, True), (2, False)):
        code = totp.totp(RFC_SECRET, now + offset * totp.PERIOD)
        assert (totp.match_step(RFC_SECRET, code, now, last_used_step=None) is not None) is ok


def test_a_step_cannot_be_used_twice_and_older_steps_are_refused() -> None:
    now = 1_700_000_000.0
    code = totp.totp(RFC_SECRET, now)
    step = totp.match_step(RFC_SECRET, code, now, last_used_step=None)
    assert step == totp.step_at(now)
    assert totp.match_step(RFC_SECRET, code, now, last_used_step=step) is None
    older = totp.totp(RFC_SECRET, now - totp.PERIOD)
    assert totp.match_step(RFC_SECRET, older, now, last_used_step=step) is None
    newer = totp.totp(RFC_SECRET, now + totp.PERIOD)
    assert totp.match_step(RFC_SECRET, newer, now, last_used_step=step) == step + 1


@pytest.mark.parametrize("bad", ["", "12345", "1234567", "12345a", "١٢٣٤٥٦", " 123456", "123 456"])
def test_malformed_codes_never_match(bad: str) -> None:
    assert totp.match_step(RFC_SECRET, bad, 1_700_000_000.0, last_used_step=None) is None


def test_provisioning_uri_is_importable_by_authenticator_apps() -> None:
    uri = totp.provisioning_uri("ABCDEFGH", account="a.b+c@example.org", issuer="EcoMind AI")
    assert uri.startswith("otpauth://totp/EcoMind%20AI:a.b%2Bc%40example.org?")
    for part in ("secret=ABCDEFGH", "issuer=EcoMind+AI", "digits=6", "period=30", "algorithm=SHA1"):
        assert part in uri


def test_encryption_round_trip_and_key_binding() -> None:
    cipher = encrypt_mfa_secret(KEY_A, "JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in cipher
    assert cipher != encrypt_mfa_secret(KEY_A, "JBSWY3DPEHPK3PXP")  # fresh nonce each time
    assert decrypt_mfa_secret(KEY_A, cipher) == "JBSWY3DPEHPK3PXP"
    with pytest.raises(DecryptionError):
        decrypt_mfa_secret(KEY_B, cipher)
    with pytest.raises(DecryptionError):
        decrypt_mfa_secret(KEY_A, "not-a-token")


def test_keyed_hash_depends_on_key_purpose_and_value() -> None:
    base = keyed_hash(KEY_A, "p", "v")
    assert base == keyed_hash(KEY_A, "p", "v") and len(base) == 64
    assert len({base, keyed_hash(KEY_B, "p", "v"), keyed_hash(KEY_A, "q", "v")}) == 3
    assert base != keyed_hash(KEY_A, "p", "w")
