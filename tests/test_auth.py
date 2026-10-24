"""Tests for the JWT claim helper."""

import base64
import json

from custom_components.bapp_auto.auth import account_identity, jwt_claims


def make_jwt(payload: dict) -> str:
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{b({'alg': 'RS256'})}.{b(payload)}.sig"


def test_jwt_claims_decodes_payload_without_verification():
    assert jwt_claims(make_jwt({"sub": "abc", "email": "a@b.ro"})) == {"sub": "abc", "email": "a@b.ro"}


def test_jwt_claims_is_empty_for_garbage():
    assert jwt_claims(None) == {}
    assert jwt_claims("not-a-jwt") == {}
    assert jwt_claims("a.b.c") == {}
    assert jwt_claims("x.W10.z") == {}  # payload "[]" is not an object


def test_account_identity_prefers_id_token_and_email():
    token = {"id_token": make_jwt({"sub": "u1", "email": "ion@firma.ro"}), "access_token": make_jwt({"sub": "u1"})}
    assert account_identity(token) == ("u1", "ion@firma.ro")


def test_account_identity_falls_back_to_access_token_and_username():
    token = {"access_token": make_jwt({"sub": "u2", "preferred_username": "ion"})}
    assert account_identity(token) == ("u2", "ion")
    assert account_identity({"access_token": "bad"}) == (None, "BAPP Auto")
