from app.core.security import hash_password, password_needs_rehash, verify_password


def test_hash_is_argon2id_and_salted() -> None:
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first.startswith("$argon2id$")
    assert first != second


def test_verify_accepts_correct_and_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_rejects_malformed_hash_without_raising() -> None:
    assert not verify_password("anything", "not-a-hash")


def test_fresh_hash_does_not_need_rehash() -> None:
    assert not password_needs_rehash(hash_password("x"))
