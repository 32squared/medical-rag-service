"""test_coaching_routes.py — RAG 코칭 영속 라우트(_rag_coaching_*) end-to-end (sqlite).

세션→플랜→체크인 라우트가 rag_db 영속 + coaching_* 이벤트로 이어지는지,
검증(누락 session_id/plan_id 400)·반환 id를 확인한다.
"""
import json
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
def route_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "cr.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    import rag_db
    monkeypatch.setattr(rag_db, "_COACHING_SCHEMA_ENSURED", False)
    return db_file


class _Fake:
    def __init__(self):
        self.responses = []

    def _send_json(self, code, payload):
        self.responses.append((code, payload))
        return (code, payload)

    def _send_error(self, code, msg):
        self.responses.append((code, {"error": msg}))
        return (code, {"error": msg})

    def _add_log(self, m):
        pass

    @property
    def last(self):
        return self.responses[-1]


def _handler(monkeypatch):
    import rag_routes
    monkeypatch.setattr(rag_routes, "RAG_ENABLED", True)

    class H(_Fake, rag_routes.RagRoutesMixin):
        pass
    return H()


def _b(d):
    return json.dumps(d).encode("utf-8")


def _rows(db, sql, args=()):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def test_session_plan_checkin_flow(route_db, monkeypatch):
    h = _handler(monkeypatch)
    # 1) 세션
    h._rag_coaching_session(_b({"track": "diet", "band": "경고", "conversation_id": "c1"}))
    code, pay = h.last
    assert code == 200 and pay["session_id"]
    sid = pay["session_id"]
    # 2) 플랜
    h._rag_coaching_plan(_b({"session_id": sid, "track": "diet",
                             "items": [{"key": "salt", "text": "저염"}], "band": "경고"}))
    code, pay = h.last
    assert code == 200 and pay["plan_id"]
    pid = pay["plan_id"]
    # 3) 체크인 2회
    h._rag_coaching_checkin(_b({"plan_id": pid, "done": True}))
    h._rag_coaching_checkin(_b({"plan_id": pid, "done": False}))
    code, pay = h.last
    assert code == 200 and pay["checkin_count"] == 2
    # 영속 + 비식별 이벤트 확인
    assert _rows(route_db, "SELECT * FROM coaching_plan WHERE plan_id=?", (pid,))
    assert len(_rows(route_db, "SELECT * FROM coaching_checkin WHERE plan_id=?", (pid,))) == 2
    ev = _rows(route_db, "SELECT event_name, track FROM analytics_events WHERE event_name LIKE 'coaching_%'")
    names = {e["event_name"] for e in ev}
    assert {"coaching_track_selected", "coaching_plan_shown", "coaching_checkin"} <= names


def test_plan_requires_session_id(route_db, monkeypatch):
    h = _handler(monkeypatch)
    h._rag_coaching_plan(_b({"track": "diet", "items": []}))
    assert h.last[0] == 400


def test_checkin_requires_plan_id(route_db, monkeypatch):
    h = _handler(monkeypatch)
    h._rag_coaching_checkin(_b({"done": True}))
    assert h.last[0] == 400
