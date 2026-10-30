"""Credentials for pseudonymous accounts (E-08): random numeric handles and invite codes, argon2id passphrases."""
import re

import pytest

from setu.web import auth


def test_handles_and_invite_codes_are_random_digits_only():
    handles = {auth.new_handle() for _ in range(200)}
    assert len(handles) == 200
    assert all(re.fullmatch(r"\d{4}-\d{4}", h) for h in handles)
    codes = {auth.new_invite_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(re.fullmatch(r"\d{4}-\d{4}-\d{4}", c) for c in codes)


def test_passphrase_is_hashed_with_argon2id_and_verifies():
    h = auth.hash_passphrase("नीला आसमान 2026")
    assert h.startswith("$argon2id$")
    assert auth.verify_passphrase(h, "नीला आसमान 2026")
    assert not auth.verify_passphrase(h, "नीला आसमान 2027")
    assert not auth.verify_passphrase("not-a-hash", "x")


@pytest.mark.parametrize("passphrase,ok", [
    ("short", False),
    ("1234-5678", False),            # the handle itself
    ("          ", False),           # whitespace only
    ("मेरा पासवर्ड", True),            # 12 characters, any script is fine
    ("x" * 201, False),
    ("सही-लंबा-वाक्यांश", True),
])
def test_passphrase_policy(passphrase, ok):
    assert (auth.passphrase_problem(passphrase, handle="1234-5678") is None) is ok


def test_tokens_are_long_and_only_their_hash_is_stored():
    token = auth.new_session_token()
    assert len(token) >= 43
    assert auth.token_hash(token) != token and len(auth.token_hash(token)) == 64
    assert auth.token_hash(token) == auth.token_hash(token)
