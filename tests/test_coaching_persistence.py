"""test_coaching_persistence.py — 코칭 영속(rag_db) + 비식별 analytics 이벤트 (18 §7.2).

임시 SQLite에 전체 마이그레이션(018 코칭테이블·019 코칭차원 포함)을 적용하고
세션→플랜→체크인 적재/조회 + coaching_* 이벤트 emit을 end-to-end 검증한다.
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
def coach_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "coach.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    import rag_db
    monkeypatch.setattr(rag_db, "_COACHING_SCHEMA_ENSURED", False)
    return db_file


def _rows(db_file, sql, args=()):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def test_create_session_persists_and_emits(coach_db):
    import rag_db
    sid = rag_db.create_coaching_session(conversation_id="c1", track="diet", band_at_start="경고")
    assert sid
    rows = _rows(coach_db, "SELECT * FROM coaching_session WHERE session_id=?", (sid,))
    assert rows and rows[0]["track"] == "diet" and rows[0]["band_at_start"] == "경고"
    ev = _rows(coach_db, "SELECT * FROM analytics_events WHERE event_name='coaching_track_selected'")
    assert ev and ev[0]["track"] == "diet" and ev[0]["risk_level"] == "경고"


def test_save_plan_roundtrips_items(coach_db):
    import rag_db
    sid = rag_db.create_coaching_session(track="exercise", band_at_start="주의")
    items = [{"key": "walk", "text": "하루 10분 걷기"}, {"key": "stair", "text": "계단 이용"}]
    pid = rag_db.save_coaching_plan(session_id=sid, track="exercise", items=items,
                                    band="주의", compliance_action="pass", target_period="2주")
    assert pid
    rows = _rows(coach_db, "SELECT * FROM coaching_plan WHERE plan_id=?", (pid,))
    assert rows
    assert json.loads(rows[0]["items_json"]) == items          # 한글 항목 원형 보존
    ev = _rows(coach_db, "SELECT * FROM analytics_events WHERE event_name='coaching_plan_shown'")
    assert ev and ev[0]["track"] == "exercise"


def test_checkins_record_and_read_ordered(coach_db):
    import rag_db
    sid = rag_db.create_coaching_session(track="habit")
    pid = rag_db.save_coaching_plan(session_id=sid, track="habit", items=[{"key": "sleep"}])
    assert rag_db.record_coaching_checkin(plan_id=pid, item_key="sleep", done=True)
    assert rag_db.record_coaching_checkin(plan_id=pid, item_key="sleep", done=True)
    assert rag_db.record_coaching_checkin(plan_id=pid, item_key="sleep", done=False)
    got = rag_db.get_coaching_checkins(pid)
    assert len(got) == 3
    assert [int(g["done"]) for g in got] == [1, 1, 0]           # 시간순
    ev = _rows(coach_db, "SELECT * FROM analytics_events WHERE event_name='coaching_checkin'")
    assert len(ev) == 3 and {int(e["checkin_done"]) for e in ev} == {0, 1}


def test_checkins_isolated_per_plan(coach_db):
    import rag_db
    sid = rag_db.create_coaching_session(track="diet")
    p1 = rag_db.save_coaching_plan(session_id=sid, track="diet", items=[])
    p2 = rag_db.save_coaching_plan(session_id=sid, track="diet", items=[])
    rag_db.record_coaching_checkin(plan_id=p1, done=True)
    assert len(rag_db.get_coaching_checkins(p1)) == 1
    assert rag_db.get_coaching_checkins(p2) == []
