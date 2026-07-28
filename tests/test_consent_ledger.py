"""test_consent_ledger.py — 동의원장(consent_db) 영속 + 순수 판정 (P0 23 §2·§4).

임시 SQLite에 마이그레이션(020 포함)을 적용하고 grant/revoke append-only 원장과
현재상태·개인화 게이트·철회권을 end-to-end 검증한다.
"""
import sqlite3
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
def consent_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "consent.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    import consent_db as cdb
    monkeypatch.setattr(cdb, "_SCHEMA_ENSURED", False)
    return cdb


# ── 순수 판정 (DB 불필요) ────────────────────────────────────

def test_resolve_current_latest_wins():
    import consent_db as cdb
    recs = [
        {"item_key": "sensitive_info", "action": "grant",  "created_at": "2026-06-01T00:00:00"},
        {"item_key": "sensitive_info", "action": "revoke", "created_at": "2026-06-02T00:00:00"},
        {"item_key": "personal_info",  "action": "grant",  "created_at": "2026-06-01T00:00:00"},
    ]
    cur = cdb.resolve_current(recs)
    assert cur["sensitive_info"]["action"] == "revoke"          # 나중 레코드 승
    assert cdb.granted_items(recs) == {"personal_info"}


def test_resolve_current_revoke_wins_tie():
    import consent_db as cdb
    # 동시각(같은 created_at) grant/revoke → 안전측(revoke) 우선, 행순서 비의존
    recs = [
        {"item_key": "sensitive_info", "action": "grant",  "created_at": "2026-06-01T00:00:00"},
        {"item_key": "sensitive_info", "action": "revoke", "created_at": "2026-06-01T00:00:00"},
    ]
    assert cdb.resolve_current(recs)["sensitive_info"]["action"] == "revoke"
    assert cdb.resolve_current(list(reversed(recs)))["sensitive_info"]["action"] == "revoke"


def test_personalization_gate():
    import consent_db as cdb
    base = [{"item_key": "personal_info", "action": "grant", "created_at": "t1"}]
    assert cdb.personalization_allowed(base) is False            # 민감 미동의 → 차단
    base.append({"item_key": "sensitive_info", "action": "grant", "created_at": "t2"})
    assert cdb.personalization_allowed(base) is True
    # 국외 LLM 경로면 cross_border 까지 필요
    assert cdb.personalization_allowed(base, cross_border_needed=True) is False
    base.append({"item_key": "cross_border", "action": "grant", "created_at": "t3"})
    assert cdb.personalization_allowed(base, cross_border_needed=True) is True


def test_missing_required():
    import consent_db as cdb
    assert cdb.missing_required([]) == ["personal_info"]
    granted = [{"item_key": "personal_info", "action": "grant", "created_at": "t1"}]
    assert cdb.missing_required(granted) == []


# ── DB 영속 ──────────────────────────────────────────────────

def test_grant_revoke_roundtrip(consent_db):
    cdb = consent_db
    s = "subj-1"
    cdb.grant(s, "personal_info")
    cdb.grant(s, "sensitive_info")
    assert cdb.is_granted(s, "sensitive_info") is True
    cdb.revoke(s, "sensitive_info", source="settings")
    assert cdb.is_granted(s, "sensitive_info") is False         # 철회 즉시 반영
    assert cdb.is_granted(s, "personal_info") is True
    assert len(cdb.history(s, "sensitive_info")) == 2           # append-only(grant+revoke)


def test_history_is_append_only(consent_db, monkeypatch):
    cdb = consent_db
    # Windows 시계 틱(~15.6ms) 안에서 3연속 insert 가 동일 created_at 을 받으면
    # 의도된 안전규칙(동시각 동률=revoke 우선)에 걸려 플레이크 → 단조증가 시계 주입
    _seq = iter(f"2026-06-01T00:00:0{i}+00:00" for i in range(10))
    monkeypatch.setattr(cdb, "_now_iso", lambda: next(_seq))
    s = "subj-2"
    cdb.grant(s, "location")
    cdb.revoke(s, "location")
    cdb.grant(s, "location")
    h = cdb.history(s, "location")
    assert [r["action"] for r in h] == ["grant", "revoke", "grant"]  # 시간순 이력 보존
    assert cdb.is_granted(s, "location") is True                     # 최종 grant


def test_same_timestamp_tie_revoke_wins(consent_db, monkeypatch):
    # 동시각 동률이 실제로 나면 안전측(revoke)이 이겨야 한다 — 규칙 자체를 고정
    monkeypatch.setattr(consent_db, "_now_iso", lambda: "2026-06-01T00:00:00+00:00")
    s = "subj-tie"
    consent_db.grant(s, "location")
    consent_db.revoke(s, "location")
    consent_db.grant(s, "location")
    assert consent_db.is_granted(s, "location") is False


def test_personalization_allowed_db_reflects_revoke(consent_db):
    cdb = consent_db
    s = "subj-3"
    cdb.grant(s, "personal_info")
    cdb.grant(s, "sensitive_info")
    assert cdb.personalization_allowed(cdb.get_records(s)) is True
    cdb.revoke(s, "sensitive_info")
    assert cdb.personalization_allowed(cdb.get_records(s)) is False  # 철회로 개인화 차단


def test_isolation_per_subject(consent_db):
    cdb = consent_db
    cdb.grant("a", "push")
    assert cdb.is_granted("a", "push") is True
    assert cdb.is_granted("b", "push") is False
    assert cdb.current_state("b") == {}
