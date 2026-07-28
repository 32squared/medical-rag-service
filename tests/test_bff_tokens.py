"""test_bff_tokens.py — BFF 세션 토큰 서명·검증(순수, HMAC)."""
import time

import pytest

from bff import tokens


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("BFF_TOKEN_SECRET", "unit-test-secret")


def test_issue_verify_roundtrip():
    t = tokens.issue_access_token("acct-1", session_id="sess-1")
    p = tokens.verify_access_token(t)
    assert p and p["sub"] == "acct-1" and p["sid"] == "sess-1"


def test_tampered_body_rejected():
    t = tokens.issue_access_token("acct-1")
    body, sig = t.split(".")
    forged = tokens._b64e(b'{"sub":"attacker","exp":9999999999}') + "." + sig
    assert tokens.verify_access_token(forged) is None


def test_tampered_signature_rejected():
    t = tokens.issue_access_token("acct-1")
    body, sig = t.split(".")
    assert tokens.verify_access_token(body + ".AAAA") is None


def test_expired_rejected():
    now = int(time.time())
    t = tokens.issue_access_token("acct-1", ttl_seconds=10, now=now - 100)
    assert tokens.verify_access_token(t, now=now) is None


def test_wrong_secret_rejected(monkeypatch):
    t = tokens.issue_access_token("acct-1")
    monkeypatch.setenv("BFF_TOKEN_SECRET", "different-secret")
    assert tokens.verify_access_token(t) is None


def test_malformed_rejected():
    assert tokens.verify_access_token("") is None
    assert tokens.verify_access_token("nodot") is None
    assert tokens.verify_access_token("a.b.c") is None


def test_refresh_token_unpredictable_and_hashed():
    r1, r2 = tokens.new_refresh_token(), tokens.new_refresh_token()
    assert r1 != r2 and len(r1) > 20
    assert tokens.hash_token(r1) == tokens.hash_token(r1)
    assert tokens.hash_token(r1) != r1            # 원본 비저장
