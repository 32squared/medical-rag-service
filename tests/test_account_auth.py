"""test_account_auth.py — 계정·세션(account_db) 영속 + CI 해시 (P0 23 §3)."""
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _apply_sqlite_migrations(db_path):
    conn = sqlite3.connect(db_path)
    for f in sorted((REPO_ROOT / "migrations").glob("*_sqlite.sql"), key=lambda p: p.name):
        for stmt in f.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            if not s or s.upper() in ("BEGIN", "COMMIT"):
                continue
            try:
                conn.execute(s)
            except Exception:
                pass
    conn.commit()
    conn.close()


@pytest.fixture
def acc_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "acc.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    import account_db as adb
    monkeypatch.setattr(adb, "_SCHEMA_ENSURED", False)
    return adb


# ── 순수: CI 해시 ────────────────────────────────────────────

def test_hash_ci_deterministic_and_keyed():
    import account_db as adb
    assert adb.hash_ci("") == ""
    h1 = adb.hash_ci("CI-RAW-123")
    assert h1 == adb.hash_ci("CI-RAW-123")            # 결정적
    assert "CI-RAW-123" not in h1                      # 원본 비노출
    keyed = adb.hash_ci("CI-RAW-123", key="secret")
    assert keyed != h1 and len(keyed) == 64            # HMAC ≠ 평문 SHA256


# ── 계정 ─────────────────────────────────────────────────────

def test_upsert_account_dedups_by_ci(acc_db):
    adb = acc_db
    ci = adb.hash_ci("CI-A", key="k")
    a1 = adb.upsert_account_by_ci(ci, di_hash="di-a")
    a2 = adb.upsert_account_by_ci(ci, di_hash="di-a")   # 동일 CI → 중복가입 식별
    assert a1 and a1 == a2
    a3 = adb.upsert_account_by_ci(adb.hash_ci("CI-B", key="k"))
    assert a3 != a1                                      # 다른 CI → 다른 계정
    assert adb.get_account(a1)["status"] == "active"


def test_withdraw_marks_status_and_revokes_sessions(acc_db):
    adb = acc_db
    aid = adb.upsert_account_by_ci(adb.hash_ci("CI-W"))
    sid = adb.create_session(aid, "refresh-hash")
    assert adb.get_active_session(sid) is not None
    assert adb.withdraw_account(aid) is True
    assert adb.get_account(aid)["status"] == "withdrawn"
    assert adb.get_active_session(sid) is None           # 탈퇴 시 세션 철회


# ── 세션 ─────────────────────────────────────────────────────

def test_session_create_and_active(acc_db):
    adb = acc_db
    sid = adb.create_session("subj-1", "rh", device="web")
    s = adb.get_active_session(sid)
    assert s and s["subject_id"] == "subj-1" and s["device"] == "web"


def test_session_expiry(acc_db):
    adb = acc_db
    sid = adb.create_session("subj-2", "rh", ttl_seconds=3600)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert adb.get_active_session(sid, now=future) is None   # 만료


def test_revoke_session_and_all(acc_db):
    adb = acc_db
    s1 = adb.create_session("subj-3", "rh1")
    s2 = adb.create_session("subj-3", "rh2")
    assert adb.revoke_session(s1) is True
    assert adb.get_active_session(s1) is None
    assert adb.get_active_session(s2) is not None
    adb.revoke_all_sessions("subj-3")
    assert adb.get_active_session(s2) is None                # 로그아웃-올
