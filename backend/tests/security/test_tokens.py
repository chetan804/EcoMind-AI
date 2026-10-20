import uuid
from datetime import timedelta

import jwt
import pytest

from app.common.time import utc_now
from app.core.exceptions import UnauthenticatedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from tests.conftest import TEST_SECRET_KEY as KEY


def token(**kwargs: object) -> str:
    params: dict[str, object] = {
        "subject": uuid.uuid4(),
        "secret_key": KEY,
        "expires_in": timedelta(minutes=5),
    }
    params.update(kwargs)
    return create_access_token(**params)  # type: ignore[arg-type]


def test_round_trip() -> None:
    subject = uuid.uuid4()
    claims = decode_access_token(token(subject=subject), secret_key=KEY)
    assert claims["sub"] == str(subject)
    assert claims["type"] == "access"


def test_expired_token_rejected() -> None:
    expired = token(now=utc_now() - timedelta(hours=1))
    with pytest.raises(UnauthenticatedError):
        decode_access_token(expired, secret_key=KEY)


def test_wrong_key_rejected() -> None:
    with pytest.raises(UnauthenticatedError):
        decode_access_token(token(), secret_key="another-secret-key-0123456789abcdef-00")


def test_tampered_payload_rejected() -> None:
    header, _payload, signature = token().split(".")
    forged_payload = jwt.utils.base64url_encode(b'{"sub":"someone-else","type":"access"}').decode()
    with pytest.raises(UnauthenticatedError):
        decode_access_token(f"{header}.{forged_payload}.{signature}", secret_key=KEY)


def test_alg_none_token_rejected() -> None:
    unsigned = jwt.encode(
        {
            "sub": "x",
            "type": "access",
            "iss": "ecomind-ai",
            "iat": utc_now(),
            "exp": utc_now() + timedelta(minutes=5),
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(UnauthenticatedError):
        decode_access_token(unsigned, secret_key=KEY)


def test_token_of_other_type_rejected() -> None:
    other = jwt.encode(
        {
            "sub": "x",
            "type": "refresh",
            "iss": "ecomind-ai",
            "iat": utc_now(),
            "exp": utc_now() + timedelta(minutes=5),
        },
        KEY,
        algorithm="HS256",
    )
    with pytest.raises(UnauthenticatedError):
        decode_access_token(other, secret_key=KEY)


def test_wrong_issuer_rejected() -> None:
    foreign = jwt.encode(
        {
            "sub": "x",
            "type": "access",
            "iss": "someone-else",
            "iat": utc_now(),
            "exp": utc_now() + timedelta(minutes=5),
        },
        KEY,
        algorithm="HS256",
    )
    with pytest.raises(UnauthenticatedError):
        decode_access_token(foreign, secret_key=KEY)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    first, second = generate_refresh_token(), generate_refresh_token()
    assert first != second and len(first) >= 43
    digest = hash_refresh_token(first)
    assert len(digest) == 64 and first not in digest
    assert digest == hash_refresh_token(first)
