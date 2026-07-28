"""
페르소나 end-to-end — '상황에 맞는 답변이 실제로 이루어지는지' 검증.

각 페르소나의 개인화 데이터(vitals)를 vital_rules.run으로 해석한 findings를
실제 generate_response 파이프라인에 personal_findings로 흘려(LLM·검색은 mock),
상황에 맞는 '📋 내 기록 참고' 블록이 답변(STOP.text)에 결정적으로 결합되는지,
무관한 질의엔 과노출되지 않는지(관련성 게이트)를 확인한다.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as vr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MARK = "## 📋 내 기록 참고"
WARN = "기준을 벗어난 구간"        # 경고 phrase
CAUTION = "관리가 권장되는 구간"   # 주의 phrase
STABLE = "특이소견이 보이지 않습니다"  # 안정 phrase


def _personas():
    with open(REPO / "test_personas" / "personas.json", encoding="utf-8") as f:
        return json.load(f)["personas"]


def _findings(pid):
    p = next(x for x in _personas() if x["id"] == pid)
    return vr.run(p["vitals"][-1], locale=p.get("locale", "KR"),
                  population=p.get("population", "adult"), context=p.get("context", "clinic"))


def _chunk(cid, content="혈압·체온·호흡 관리에 대한 일반 의료 정보입니다.", score=0.62):
    return {"chunk_id": cid, "document_id": f"d_{cid}", "content": content,
            "section_path": [], "source_id": "test_src", "evidence_level": "B",
            "evidence_topic": "fever", "severity": None, "score": score, "boost_reasons": []}


def _provider():
    m = MagicMock()
    m.provider_id = "openai_gpt5"
    m.model_id = "gpt-5"

    def se(system, user, **k):
        yield {"type": "GENERATION", "text": "일반적인 건강 안내입니다. [1]"}
        yield {"type": "STOP", "text": "일반적인 건강 안내입니다. [1]",
               "tokens": {"input": 10, "output": 5}}

    m.stream_chat.side_effect = se
    return m


def _run(query, findings):
    analysis = MagicMock()
    analysis.violations = []
    with patch("rag_engine.hybrid_search", return_value=[_chunk("C1"), _chunk("C2")]), \
         patch("llm_router.get_llm_provider", return_value=_provider()), \
         patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
         patch("rag_engine._set_conversation_state"), \
         patch("rag_engine._insert_rag_query", return_value="rq-e2e"), \
         patch("analyzer.ComplianceAnalyzer") as MA:
        MA.return_value.analyze.return_value = analysis
        from rag_engine import generate_response
        evs = list(generate_response(query=query, conversation_id="c-e2e",
                                     personal_findings=findings))
    stop = next(e for e in evs if e["type"] == "STOP")
    return stop["text"]


def _block(text):
    return text.split(MARK)[1] if MARK in text else ""


# ── 상황에 맞는 개인화 결합 ──────────────────────────────────
def test_hypertension_warns_on_bp_query():
    t = _run("혈압이 높게 나왔는데 괜찮을까요?", _findings("hypertension_senior"))
    assert MARK in t and "혈압" in _block(t) and WARN in _block(t)


def test_fever_warns_on_fever_query():
    t = _run("열이 39도까지 오르고 몸살이 나요", _findings("fever_adult"))
    assert MARK in t and "체온" in _block(t) and WARN in _block(t)


def test_respiratory_surfaces_only_relevant_signal():
    # 비응급 호흡기 표현(기침·가래) — spo2 scope만 건드림
    t = _run("기침이 오래가고 가래가 많아요", _findings("respiratory_lowspo2"))
    blk = _block(t)
    assert MARK in t and "산소포화도" in blk and CAUTION in blk
    # 무관 신호(체온 주의)는 표면화하지 않음 — 과노출 차단
    assert "체온" not in blk


def test_emergency_query_suppresses_personalization():
    # 응급 적신호(숨이 차다) 질의 → 개인화 결합 억제(I7)
    t = _run("숨이 차고 가슴이 답답해서 쓰러질 것 같아요", _findings("respiratory_lowspo2"))
    assert MARK not in t


def test_healthy_reassures_on_related_query():
    # '두통'은 혈압 scope 키워드 → 안정 라벨이 안심 문구로 결합
    t = _run("머리가 자주 아파요 두통이 있어요", _findings("healthy_office"))
    assert MARK in t and STABLE in _block(t)


# ── 과노출 차단(상황 무관 시 결합 안 함) ─────────────────────
def test_unrelated_query_suppresses_block():
    t = _run("감기약 아무거나 먹어도 되나요?", _findings("hypertension_senior"))
    assert MARK not in t


def test_no_findings_no_block():
    # 소아 보호자 → findings 0 → 개인화 결합 없음
    assert _findings("pediatric_guardian") == []
    t = _run("아이가 열이 나요", _findings("pediatric_guardian"))
    assert MARK not in t


def test_raw_values_never_in_answer():
    # 원시 측정값(152, 96 등)이 답변 어디에도 노출되지 않아야 한다(I1)
    t = _run("혈압이 높게 나왔어요", _findings("hypertension_senior"))
    for raw in ("152", "96", "182", "118"):
        assert raw not in t
