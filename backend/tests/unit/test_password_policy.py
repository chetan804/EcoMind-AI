from app.modules.auth.policy import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, password_problems

EMAIL, NAME = "ada.lovelace@example.org", "Ada Lovelace"


def test_acceptable_passphrase() -> None:
    assert password_problems("correct horse battery staple", email=EMAIL, full_name=NAME) == []


def test_length_bounds() -> None:
    assert password_problems("a1" * 5, email=EMAIL, full_name=NAME)
    boundary = "xK9#" * (MIN_PASSWORD_LENGTH // 4)
    assert len(boundary) == MIN_PASSWORD_LENGTH
    assert password_problems(boundary, email=EMAIL, full_name=NAME) == []
    assert password_problems("xK9#" * 40, email=EMAIL, full_name=NAME)  # > MAX
    assert MAX_PASSWORD_LENGTH == 128


def test_common_and_repetitive_passwords_are_rejected() -> None:
    assert password_problems("Password123456", email=EMAIL, full_name=NAME)  # case-insensitive
    assert password_problems("abababababababab", email=EMAIL, full_name=NAME)


def test_personal_information_is_rejected() -> None:
    assert password_problems("my-ada.lovelace-secret!", email=EMAIL, full_name=NAME)
    assert password_problems("Ada Lovelace rocks 99", email="x@y.org", full_name=NAME)
    # Short local parts are not matched (would reject too much).
    assert password_problems("correct horse battery staple", email="ab@y.org", full_name="Al") == []


def test_no_composition_rules_are_imposed() -> None:
    assert password_problems("alllowercasewordsonly", email=EMAIL, full_name=NAME) == []
