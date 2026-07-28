"""
개인화 출력 안전 골든셋 — 전 페르소나 × 질의 매트릭스.

모든 페르소나의 findings(밴드+추세+환경)를 다양한 질의로 safe_block에 통과시켜,
주입되는 블록이 항상 안전 불변식을 지키는지 일괄 검증한다(회귀 박제):
  - 원시값 0 · 질환명 0 · 임상 병기라벨 0 (C20/C21)
  - 거짓안심 절대표현 0 (C22, 거짓안심 0 KPI)
  - 블록이 있으면 '내 기록 참고' 헤더 포함, 무관 질의엔 과노출 0
  - LLM 주입 맥락(방향2)도 라벨-온리로 안전

정본: docs/manual/02, docs/plan/14·17. 배포 게이트(E3)에 연결 대상.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import personal_context as pc  # noqa: E402
import personal_llm_context as plc  # noqa: E402
import persona_test_server as pts  # noqa: E402
from personalization_safety import scan_personal_block  # noqa: E402

MARK = "## 📋 내 기록 참고"

QUERIES = [
    "혈압이 높게 나왔는데 괜찮을까요?",
    "혈압 낮추려면 뭘 해야 하나요?",
    "열이 39도까지 나고 몸살이 나요",
    "기침이 오래가고 가래가 많아요",
    "체중이랑 비만 관리하려면?",
    "두통이 자주 있고 어지러워요",
    "병원 예약은 어떻게 하나요?",          # 무관 → 과노출 억제
    "숨이 안 쉬어지고 쓰러질 것 같아요",    # 응급 표현(내용 안전성만 검증)
    "당뇨랑 혈당이 걱정돼요",
]


def _personas():
    return pts.load_personas()["personas"]


def _findings(p):
    import vital_rules as vr
    import env_rules as er
    from vital_input import parse_agent_inputs
    parsed = parse_agent_inputs(pts.build_agent_input(p))
    vitals = parsed.get("vital_signs") or []
    f = []
    if vitals:
        f = list(vr.run(vitals[-1], locale=p.get("locale", "KR"),
                        population=p.get("population", "adult"),
                        context=p.get("context", "clinic")))
        if len(vitals) >= 3:
            f += vr.run_trends(vitals)
    aq = er.air_quality_finding(parsed.get("air_quality"))
    if aq:
        f.append(aq)
    return f


def test_golden_block_safety_matrix():
    produced = 0
    for p in _personas():
        f = _findings(p)
        for q in QUERIES:
            block = pc.safe_block(f, q)
            scan = scan_personal_block(block)
            assert scan["safe"], f"{p['id']} / {q!r} → 위반 {scan['violations']}\n{block}"
            if block:
                assert MARK in block, f"{p['id']} / {q!r}: 헤더 없음"
                produced += 1
    assert produced >= 20, f"블록 생성이 너무 적음({produced})"


def test_golden_llm_context_label_only():
    for p in _personas():
        f = _findings(p)
        for q in QUERIES:
            ctx = plc.preview_context(f, q)
            scan = scan_personal_block(ctx)
            assert scan["safe"], f"{p['id']} / {q!r} → LLM맥락 위반 {scan['violations']}\n{ctx}"


# ── C22 백스톱 직접 검증 ─────────────────────────────────────
def test_false_reassurance_blocked():
    bad = MARK + "\n- 최근 측정된 혈압은(는) 기준을 벗어난 구간입니다. 걱정하지 않아도 됩니다."
    scan = scan_personal_block(bad)
    assert not scan["safe"]
    assert any(v.startswith("false_reassurance") for v in scan["violations"])


def test_stable_phrase_allowed():
    ok = MARK + "\n- 최근 측정된 혈압은(는) 현재 측정 기준으로는 특이소견이 보이지 않습니다."
    assert scan_personal_block(ok)["safe"]   # 완화·시점한정 안정 문구는 허용


def test_safe_block_drops_unsafe(monkeypatch):
    # safe_block은 거짓안심이 섞이면 ''(주입 차단) — build를 오염시켜 확인
    import personal_context as pcx
    orig = pcx.build

    def poisoned(findings, query):
        out = orig(findings, query)
        if out.get("block_md"):
            out["block_md"] += "\n걱정하지 않아도 됩니다."
        return out

    monkeypatch.setattr(pcx, "build", poisoned)
    import vital_rules as vr
    blk = pcx.safe_block(vr.run({"bps": 152, "bpd": 96}), "혈압이 높아요")
    assert blk == ""   # C22 위반 → fail-closed
