"""test_bff_prod_guards.py — 프로덕션 fail-closed 보안 가드 (감사 지적 반영).

APP_ENV=prod 에서 보안 필수 설정(토큰비밀·CI HMAC 키·실 PASS provider) 누락이면
부팅/서명/해시가 차단되는지. dev(기본)에서는 폴백 허용.
"""
import pytest


def test_token_secret_required_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BFF_TOKEN_SECRET", raising=False)
    from bff import tokens
    with pytest.raises(RuntimeError):
        tokens.issue_access_token("acct")          # _secret() fail-closed


def test_token_secret_rejects_dev_default_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    from bff import tokens
    monkeypatch.setenv("BFF_TOKEN_SECRET", tokens._DEV_SECRET)
    with pytest.raises(RuntimeError):
        tokens.issue_access_token("acct")          # 공개 기본키 거부


def test_ci_hmac_key_required_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("ACCOUNT_CI_HMAC_KEY", raising=False)
    import account_db
    with pytest.raises(RuntimeError):
        account_db.hash_ci("CI-RAW-123")           # 무키 SHA256 폴백 차단


def test_ci_hmac_ok_in_prod_with_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ACCOUNT_CI_HMAC_KEY", "rotation-key")
    import account_db
    assert len(account_db.hash_ci("CI-RAW-123")) == 64


def test_mock_pass_blocked_in_prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("ALLOW_MOCK_AUTH", raising=False)
    import bff.pass_adapter as pa
    assert pa.PROVIDER == "mock"
    with pytest.raises(RuntimeError):
        pa.start_verification()
    with pytest.raises(RuntimeError):
        pa.verify("tx")


def test_mock_pass_allowed_with_explicit_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALLOW_MOCK_AUTH", "1")
    import bff.pass_adapter as pa
    assert pa.start_verification()["mock"] is True   # 명시 허용 시 통과


def test_create_app_fails_in_prod_without_config(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BFF_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ACCOUNT_CI_HMAC_KEY", raising=False)
    from bff.app import create_app
    with pytest.raises(RuntimeError):
        create_app()


def test_dev_allows_defaults(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("BFF_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("ACCOUNT_CI_HMAC_KEY", raising=False)
    from bff import tokens
    import account_db
    assert tokens.issue_access_token("acct")         # dev 폴백 허용
    assert len(account_db.hash_ci("CI")) == 64        # dev SHA256 폴백 허용
