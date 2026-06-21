"""
후속 질문 제안(멀티턴 버튼) — followups.suggest + wraith STOP 통과 + 페르소나 preview.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import followups as fu  # noqa: E402


def test_topic_bp():
    s = fu.suggest("혈압이 높게 나왔어요")
    assert s and len(s) <= 3 and any("혈압" in x for x in s)


def test_topic_fever():
    assert any(("해열제" in x) or ("응급실" in x) for x in fu.suggest("열이 39도까지 나요"))


def test_generic_when_no_topic():
    s = fu.suggest("그냥 좀 궁금한 게 있어요")
    assert len(s) == 3 and any("진료과" in x for x in s)


def test_deterministic_and_capped():
    assert fu.suggest("혈압 두통", max_n=2) == fu.suggest("혈압 두통", max_n=2)
    assert len(fu.suggest("혈압 두통 기침 혈당", max_n=3)) == 3


def test_dedup():
    s = fu.suggest("혈압 어지럼")
    assert len(s) == len(set(s))


def test_empty_query_still_suggests():
    assert fu.suggest("")   # 빈 질의도 일반 후속 제공(빈 버튼 방지)


def test_adapter_passes_followups():
    from wraith_sse_adapter import adapt_event
    evs = adapt_event({"type": "STOP", "followups": ["a", "b"],
                       "tokens": {"input": 1, "output": 1}})
    stop = [e for e in evs if e["type"] == "STOP"][0]
    assert stop.get("followups") == ["a", "b"]
    # followups 없으면 STOP은 그대로 bare
    evs2 = adapt_event({"type": "STOP", "tokens": {}})
    assert evs2[-1] == {"type": "STOP"}


def test_persona_preview_has_followups():
    import persona_test_server as pts
    p = next(x for x in pts.load_personas()["personas"] if x["id"] == "hypertension_senior")
    out = pts.compute_preview(p, "혈압 낮추려면?")
    assert out["followups"] and any("혈압" in x for x in out["followups"])
