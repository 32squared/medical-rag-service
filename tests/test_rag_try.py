"""
rag_try 하니스 스모크 테스트 — 오프라인 RAG 테스트 도구가 동작하는지 보호.
"""

from rag_try import run_turn


def _ctx():
    return {"last_symptom_keys": [], "turn_count": 0}


def test_symptom_query_gives_navigation():
    t = run_turn("배가 아파요", _ctx())
    r = t["result"]
    assert r["safety_level"] == "insufficient_information"
    assert r["triage"]["departments"]          # 진료과 안내
    assert "진료" in r["answer"]


def test_emergency_detected_offline():
    t = run_turn("숨을 못 쉬겠어요", _ctx())
    assert t["result"]["safety_level"] == "emergency_guidance"
    assert "119" in t["result"]["answer"]
    assert t["rewrite_method"] == "none"        # 응급은 재작성 안 함


def test_crisis_detected_offline():
    t = run_turn("죽고 싶어요", _ctx())
    assert t["result"]["safety_level"] == "crisis_guidance"
    assert "109" in t["result"]["answer"]


def test_multiturn_followup_rewrites():
    ctx = _ctx()
    run_turn("머리가 아파요", ctx)               # 주제: 두통
    t2 = run_turn("약은 먹어도 되나요?", ctx)     # 후속
    assert t2["rewrite_method"] == "rule"
    assert "두통" in t2["retrieval_query"]


def test_context_carries_forward():
    ctx = _ctx()
    run_turn("기침이 나요", ctx)
    assert ctx["turn_count"] == 1
    assert ctx["last_symptom_keys"]              # 주제 보존
