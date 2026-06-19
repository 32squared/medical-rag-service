"""
conversation_context 테스트 (06-multiturn-design.md §3/§4).

- name_for_key / last_symptom_name: 증상키 → 한글명 (카탈로그 의존, DB 불요)
- load/update 라운드트립: 임시 SQLite로 세션 컨텍스트 영속·turn_count 증가 검증
"""

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conversation_context as cc


# ── 이름 변환 (DB 불요) ───────────────────────────────────────────────────────

def test_name_for_key_resolves_known_symptom():
    """카탈로그에 있는 임의 증상키 → 그 카탈로그의 symptom_name과 일치."""
    from symptom_catalog import load_catalog
    catalog = load_catalog()
    assert catalog, "카탈로그가 비어있음"
    key = next(iter(catalog))
    expected = catalog[key].get("symptom_name") or ""
    assert cc.name_for_key(key) == expected


def test_name_for_key_unknown_returns_empty():
    assert cc.name_for_key("___no_such_key___") == ""
    assert cc.name_for_key("") == ""


def test_last_symptom_name_from_context():
    from symptom_catalog import load_catalog
    key = next(iter(load_catalog()))
    ctx = {"last_symptom_keys": [key], "last_intent": None,
           "last_departments": [], "turn_count": 1}
    assert cc.last_symptom_name(ctx) == cc.name_for_key(key)


def test_last_symptom_name_empty_context():
    assert cc.last_symptom_name({"last_symptom_keys": []}) == ""
    assert cc.last_symptom_name({}) == ""


# ── DB 라운드트립 (임시 SQLite) ───────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "ctx_test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    import rag_db
    rag_db.ensure_rag_schema()
    return db_file


def test_load_empty_when_no_row(temp_db):
    ctx = cc.load_context("conv-none")
    assert ctx["turn_count"] == 0
    assert ctx["last_symptom_keys"] == []


def test_update_then_load_roundtrip(temp_db):
    cc.update_context("conv-1", symptom_keys=["headache"],
                      intent="symptom_info", departments=["신경과"])
    ctx = cc.load_context("conv-1")
    assert ctx["last_symptom_keys"] == ["headache"]
    assert ctx["last_intent"] == "symptom_info"
    assert ctx["last_departments"] == ["신경과"]
    assert ctx["turn_count"] == 1


def test_turn_count_increments(temp_db):
    cc.update_context("conv-2", symptom_keys=["cough"], intent="symptom_info")
    cc.update_context("conv-2", symptom_keys=["fever"], intent="symptom_info")
    ctx = cc.load_context("conv-2")
    assert ctx["turn_count"] == 2
    # 최신 턴 값으로 갱신됨
    assert ctx["last_symptom_keys"] == ["fever"]


# ── resolve_retrieval_query / keys_to_persist (DB는 monkeypatch) ──────────────

def test_resolve_emergency_intent_no_rewrite(monkeypatch):
    """emergency intent면 컨텍스트가 있어도 재작성하지 않는다(안전 §6-1)."""
    monkeypatch.setattr(cc, "load_context", lambda cid: {
        "last_symptom_keys": ["headache"], "last_intent": "symptom_info",
        "last_departments": ["신경과"], "turn_count": 2})
    out = cc.resolve_retrieval_query("가슴이 너무 아파요", "c", intent="emergency")
    assert out["retrieval_query"] == "가슴이 너무 아파요"
    assert out["rewrite_method"] == "none"


def test_resolve_followup_rewrites(monkeypatch):
    """직전 주제가 있고 후속 신호면 검색 질의가 재작성된다."""
    monkeypatch.setattr(cc, "load_context", lambda cid: {
        "last_symptom_keys": ["headache"], "last_intent": "symptom_info",
        "last_departments": ["신경과"], "turn_count": 1})
    out = cc.resolve_retrieval_query("언제 병원 가야 해요?", "c", intent="unknown")
    assert out["is_followup"] is True
    assert out["rewrite_method"] == "rule"
    assert out["retrieval_query"] != "언제 병원 가야 해요?"


def test_resolve_non_followup_when_query_has_symptom(monkeypatch):
    """질의 자체에 증상이 잡히면 재작성하지 않는다."""
    monkeypatch.setattr(cc, "load_context", lambda cid: {
        "last_symptom_keys": ["headache"], "turn_count": 1,
        "last_intent": None, "last_departments": []})
    out = cc.resolve_retrieval_query("배가 아파요", "c", intent="symptom_info")
    assert out["is_followup"] is False
    assert out["retrieval_query"] == "배가 아파요"


def test_resolve_first_turn_no_rewrite(monkeypatch):
    monkeypatch.setattr(cc, "load_context", lambda cid: {
        "last_symptom_keys": [], "turn_count": 0,
        "last_intent": None, "last_departments": []})
    out = cc.resolve_retrieval_query("언제 병원 가야 해요?", "c", intent="unknown")
    assert out["is_followup"] is False
    assert out["rewrite_method"] == "none"


def test_keys_to_persist_prefers_current():
    assert cc.keys_to_persist(["fever"], {"last_symptom_keys": ["headache"]}) == ["fever"]


def test_keys_to_persist_carries_forward_on_followup():
    """현재 턴에 증상이 없으면(후속) 직전 주제를 유지한다."""
    assert cc.keys_to_persist([], {"last_symptom_keys": ["headache"]}) == ["headache"]


def test_keys_to_persist_empty():
    assert cc.keys_to_persist([], {}) == []


def test_context_does_not_touch_emergency_state(temp_db):
    """컨텍스트 갱신이 emergency_state를 건드리지 않아야 한다."""
    import rag_db
    rag_db.set_conversation_state("conv-3", "EMERGENCY_REDIRECTED")
    cc.update_context("conv-3", symptom_keys=["chest_pain"], intent="emergency")
    state = rag_db.get_conversation_state("conv-3")
    assert state["emergency_state"] == "EMERGENCY_REDIRECTED"
