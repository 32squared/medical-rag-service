"""
답변 명시 피드백(👍/👎) — response_feedback + /api/rag/feedback + thumbs 이벤트.

마이그레이션 016 테이블, rag_db.record_response_feedback(영속 + 비식별 thumbs 이벤트),
그리고 라우트 핸들러(_rag_feedback)를 임시 SQLite로 end-to-end 검증한다.
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
def fb_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "fb.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    return db_file


def _q(db_file, sql, params=()):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


# ── 데이터 레이어 ────────────────────────────────────────────
def test_table_exists(fb_db):
    cols = {r["name"] for r in _q(fb_db, "PRAGMA table_info(response_feedback)")}
    for c in ("rag_query_id", "rating", "reason_code", "created_at"):
        assert c in cols


def test_record_persists_and_emits_event(fb_db):
    import rag_db
    fid = rag_db.record_response_feedback(
        "rq-1", "up", conversation_id="c1", user_id="u1", reason_code="helpful")
    assert fid
    rows = _q(fb_db, "SELECT * FROM response_feedback WHERE id=?", (fid,))
    assert len(rows) == 1
    assert rows[0]["rating"] == "up"
    assert rows[0]["reason_code"] == "helpful"
    # 비식별 thumbs_up 이벤트가 함께 적재됐는지
    ev = _q(fb_db, "SELECT * FROM analytics_events WHERE event_name='thumbs_up' AND rag_query_id='rq-1'")
    assert len(ev) == 1


def test_record_down_emits_thumbs_down(fb_db):
    import rag_db
    assert rag_db.record_response_feedback("rq-2", "down", conversation_id="c2")
    ev = _q(fb_db, "SELECT * FROM analytics_events WHERE event_name='thumbs_down' AND rag_query_id='rq-2'")
    assert len(ev) == 1


def test_record_rejects_bad_rating(fb_db):
    import rag_db
    assert rag_db.record_response_feedback("rq-3", "meh") is None
    assert rag_db.record_response_feedback("", "up") is None
    assert _q(fb_db, "SELECT COUNT(*) AS n FROM response_feedback")[0]["n"] == 0


# ── 라우트 핸들러 ────────────────────────────────────────────
class _FakeHandler:
    def __init__(self, user):
        self._user = user
        self.headers = {}
        self.responses = []

    def _get_tester_info(self):
        return self._user

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


def _make_handler(user, monkeypatch):
    import rag_routes
    monkeypatch.setattr(rag_routes, "RAG_ENABLED", True)

    class H(_FakeHandler, rag_routes.RagRoutesMixin):
        pass
    return H(user)


def test_endpoint_happy_path(fb_db, monkeypatch):
    h = _make_handler({"id": "u1", "name": "U1"}, monkeypatch)
    body = json.dumps({"rag_query_id": "rq-e1", "rating": "up",
                       "reason_code": "helpful", "conversation_id": "c1"}).encode("utf-8")
    h._rag_feedback(body)
    code, payload = h.last
    assert code == 200 and payload["status"] == "success" and payload["feedback_id"]
    rows = _q(fb_db, "SELECT * FROM response_feedback WHERE rag_query_id='rq-e1'")
    assert len(rows) == 1 and rows[0]["user_id"] == "u1"


def test_endpoint_validates(fb_db, monkeypatch):
    h = _make_handler({"id": "u1"}, monkeypatch)
    h._rag_feedback(json.dumps({"rating": "up"}).encode("utf-8"))        # rag_query_id 누락
    assert h.last[0] == 400
    h._rag_feedback(json.dumps({"rag_query_id": "x", "rating": "ok"}).encode("utf-8"))  # 잘못된 rating
    assert h.last[0] == 400
    assert _q(fb_db, "SELECT COUNT(*) AS n FROM response_feedback")[0]["n"] == 0


def test_endpoint_does_not_store_comment_text(fb_db, monkeypatch):
    # 호출자가 free-text comment를 보내도 저장되지 않는다(비식별 — 컬럼 없음).
    h = _make_handler({"id": "u1"}, monkeypatch)
    body = json.dumps({"rag_query_id": "rq-e2", "rating": "down",
                       "comment": "민감한 자유 텍스트 코멘트"}).encode("utf-8")
    h._rag_feedback(body)
    assert h.last[0] == 200
    row = _q(fb_db, "SELECT * FROM response_feedback WHERE rag_query_id='rq-e2'")[0]
    joined = " ".join(str(v) for v in dict(row).values())
    assert "민감한" not in joined
