import pytest
from platform_core.security.passwords import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    hashed = hash_password("correcthorsebattery9")
    assert verify_password("correcthorsebattery9", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_password_too_short_rejected():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("short1")


def test_password_too_predictable_rejected():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("password123")


def test_password_matching_user_inputs_rejected():
    with pytest.raises(WeakPasswordError):
        validate_password_strength("anaana@test.com", user_inputs=["ana@test.com", "Ana"])


def test_strong_password_accepted():
    # No debe lanzar
    validate_password_strength("Xk9#mQz7$vLp2Rt", user_inputs=["ana@test.com"])
