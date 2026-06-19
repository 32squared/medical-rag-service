"""
멀티턴 재작성 감사 영속 (06-multiturn-design.md §6-4).

마이그레이션 013이 rag_queries에 추가한 rewrite_method·rewritten_from 컬럼에
update_rag_query_audit가 값을 영속하는지 임시 SQLite로 검증한다.
"""

import glob
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _apply_sqlite_migrations(db_path: str):
    conn = sqlite3.connect(db_path)
    for f in sorted((REPO_ROOT / "migrations").glob("*_sqlite.sql"), key=lambda p: p.name):
        for stmt in f.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            if not s or s.upper() in ("BEGIN", "COMMIT"):
                continue
            lines = [l for l in s.splitlines() if l.strip() and not l.strip().startswith("--")]
            if not lines:
                continue
            try:
                conn.execute(s)
            except Exception:
                pass
    conn.commit()
    conn.close()


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "audit.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    return db_file


def test_audit_columns_exist(audit_db):
    conn = sqlite3.connect(audit_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(rag_queries)")}
    conn.close()
    assert "rewrite_method" in cols
    assert "rewritten_from" in cols


def test_audit_persists_rewrite_fields(audit_db):
    conn = sqlite3.connect(audit_db)
    conn.execute(
        "INSERT INTO rag_queries (id, query_text, retrieved_chunk_ids, created_at) "
        "VALUES (?,?,?,?)",
        ("rq-x", "언제 병원 가야 해요?", "[]", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    import rag_db
    ok = rag_db.update_rag_query_audit("rq-x", rewrite_method="rule", rewritten_from="abc123def")
    assert ok

    conn = sqlite3.connect(audit_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT rewrite_method, rewritten_from FROM rag_queries WHERE id='rq-x'"
    ).fetchone()
    conn.close()
    assert row["rewrite_method"] == "rule"
    assert row["rewritten_from"] == "abc123def"
