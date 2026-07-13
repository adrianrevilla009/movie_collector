import uuid

import jwt
import pytest
from platform_core.security.tokens import (
    create_access_token,
    decode_access_token,
    generate_one_time_token,
    generate_refresh_token,
    hash_refresh_token,
)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "user")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_access_token_invalid_signature_rejected():
    token = create_access_token(uuid.uuid4(), "user")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered)


def test_refresh_token_never_stores_plaintext_equal_to_hash():
    raw, token_hash = generate_refresh_token()
    assert raw != token_hash
    assert hash_refresh_token(raw) == token_hash


def test_refresh_token_is_sufficiently_random():
    raw1, _ = generate_refresh_token()
    raw2, _ = generate_refresh_token()
    assert raw1 != raw2


def test_one_time_token_hash_matches_manual_hash():
    raw, token_hash = generate_one_time_token()
    assert hash_refresh_token(raw) == token_hash
