"""
비식별 이벤트 스토어 (개선 루프 E2) — analytics_events.

마이그레이션 015가 만든 analytics_events에 emit()이 화이트리스트 차원만 적재하고,
원문·원시값·진단명 등 비허용 키는 폐기하는지(구조적 비식별) 임시 SQLite로 검증한다.
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
def ev_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "events.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    return db_file


def _rows(db_file, where=""):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM analytics_events {where}").fetchall()
    conn.close()
    return rows


def test_table_exists(ev_db):
    conn = sqlite3.connect(ev_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(analytics_events)")}
    conn.close()
    for c in ("event_name", "intent", "gate_decision", "citations_count",
              "is_followup", "refusal", "emergency", "created_at"):
        assert c in cols


def test_emit_writes_whitelisted_row(ev_db):
    import analytics_events as ae
    eid = ae.emit("answer_shown", conversation_id="c1", rag_query_id="rq1",
                  intent="symptom_triage", primary_domain="respiratory",
                  risk_level="medium", guardrail_action="pass",
                  gate_decision="PASS", evidence_quality="high",
                  citations_count=3, latency_ms=1200,
                  is_followup=True, had_personal_block=False,
                  gave_referral=True, refusal=False, emergency=False)
    assert eid
    rows = _rows(ev_db)
    assert len(rows) == 1
    r = rows[0]
    assert r["event_name"] == "answer_shown"
    assert r["intent"] == "symptom_triage"
    assert r["primary_domain"] == "respiratory"
    assert r["citations_count"] == 3
    assert r["latency_ms"] == 1200
    assert r["is_followup"] == 1
    assert r["gave_referral"] == 1
    assert r["refusal"] == 0


def test_emit_rejects_unknown_event(ev_db):
    import analytics_events as ae
    assert ae.emit("bogus_event", conversation_id="c1", intent="x") is None
    assert len(_rows(ev_db)) == 0


def test_sanitize_drops_forbidden_keys():
    import analytics_events as ae
    clean = ae.sanitize({
        "intent": "symptom_triage",
        "query_text": "내 혈압 165/92 인데 고혈압인가요?",   # 원문 — 폐기
        "raw_value": "165/92",                                # 원시값 — 폐기
        "diagnosis": "고혈압",                                 # 진단명 — 폐기
        "citations_count": 2,
    })
    assert clean == {"intent": "symptom_triage", "citations_count": 2}


def test_sanitize_coerces_types():
    import analytics_events as ae
    clean = ae.sanitize({"is_followup": True, "refusal": 0,
                         "citations_count": "5", "intent": "  info  "})
    assert clean["is_followup"] == 1
    assert clean["refusal"] == 0
    assert clean["citations_count"] == 5
    assert clean["intent"] == "info"


def test_emit_ignores_forbidden_kwargs(ev_db):
    import analytics_events as ae
    # 호출자가 실수로 원문·진단명을 넘겨도 컬럼이 없어 저장 안 됨(예외도 없음)
    eid = ae.emit("insufficient_evidence", conversation_id="c2",
                  intent="info_lookup", refusal=True,
                  query_text="민감한 질문 원문", diagnosis="당뇨병")
    assert eid
    rows = _rows(ev_db, "WHERE conversation_id='c2'")
    assert len(rows) == 1
    joined = " ".join(str(v) for v in dict(rows[0]).values())
    assert "민감한" not in joined and "당뇨병" not in joined
    assert rows[0]["refusal"] == 1


def test_rag_engine_emit_from_classification(ev_db):
    import rag_engine
    rag_engine._emit_analytics(
        "answer_shown", "c3",
        {"intent": "drug_safety", "medical_domains": ["drug_safety", "cardio"],
         "risk_level": "high", "requires_clinician_consult": True},
        rag_query_id="rq3", guardrail_action="pass",
        gate_result={"decision": "PASS", "evidence_quality": "high"},
        citations_count=4, latency_ms=900, is_followup=False,
        had_personal_block=True, gave_referral=True, refusal=False, emergency=False,
    )
    rows = _rows(ev_db, "WHERE conversation_id='c3'")
    assert len(rows) == 1
    r = rows[0]
    assert r["intent"] == "drug_safety"
    assert r["primary_domain"] == "drug_safety"   # medical_domains[0]
    assert r["risk_level"] == "high"
    assert r["gate_decision"] == "PASS"
    assert r["evidence_quality"] == "high"
    assert r["had_personal_block"] == 1
