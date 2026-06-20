"""personal_context.build 단위 테스트 — 관련성 게이트 + 안전 렌더(원시값·질환명 0)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_context import build, relevance_gate, safe_block
from vital_rules import run


def _finding(signal, label, cite="ref.x"):
    return {"signal_key": signal, "label_user": label, "cite_doc_id": cite, "match": "ok"}


# ── 관련성 게이트 (과노출 차단) ──────────────────────────────────

def test_relevance_gate_surfaces_only_matching_scope():
    findings = [_finding("blood_pressure", "경고"), _finding("heart_rate", "안정")]
    kept = relevance_gate("요즘 혈압이 좀 걱정돼요", findings)
    sigs = {f["signal_key"] for f in kept}
    assert sigs == {"blood_pressure"}   # 심박은 질의에 없음 → 미표면화


def test_unrelated_query_yields_empty_block():
    findings = [_finding("blood_pressure", "경고"), _finding("bmi", "주의")]
    out = build(findings, "오늘 점심 뭐 먹을까요")
    assert out["block_md"] == ""
    assert out["surfaced"] == []


def test_symptom_keyword_bridges_to_signal():
    # 증상 키워드(두통)도 혈압 scope로 매칭(indirect 브리징)
    out = build([_finding("blood_pressure", "주의")], "두통이 자꾸 있어요")
    assert out["surfaced"] and out["surfaced"][0]["signal_key"] == "blood_pressure"


def test_no_match_or_denied_findings_never_surface():
    # 라벨 없는 finding(no_match/denied)은 게이트 통과 못 함
    bad = [{"signal_key": "blood_pressure", "label_user": None, "cite_doc_id": "x"}]
    assert relevance_gate("혈압", bad) == []


# ── 안전 렌더 (I1 원시값 0 · I12 질환명 0) ───────────────────────

def test_block_has_no_raw_values():
    # findings는 라벨만 보유하므로 블록에 수치가 없어야 함
    out = build([_finding("blood_pressure", "경고")], "혈압")
    for raw in ("120", "140", "165", "80", "90"):
        assert raw not in out["block_md"]


def test_block_has_no_disease_names():
    out = build([_finding("blood_pressure", "경고"), _finding("fasting_glucose", "경고")],
                "혈압이랑 당뇨가 걱정이에요")
    for disease in ("고혈압", "당뇨병", "비만", "저산소"):
        assert disease not in out["block_md"]


def test_warning_label_includes_clinician_referral():
    out = build([_finding("blood_pressure", "경고")], "혈압")
    assert "의료진" in out["block_md"]


def test_block_has_measurement_time_framing_and_closing():
    out = build([_finding("bmi", "주의")], "체중이 늘었어요")
    assert "최근 측정" in out["block_md"]
    assert "의료진과 상담" in out["block_md"]
    assert out["block_md"].startswith("## 📋 내 기록 참고")


def test_cite_doc_ids_returned_for_wiring():
    out = build([_finding("blood_pressure", "경고", cite="bp.adult.kr.ksh2022")], "혈압")
    assert out["cite_doc_ids"] == ["bp.adult.kr.ksh2022"]


def test_no_placeholder_citation_markers_in_preview():
    # 11 §5: 가짜 [N] 마커 금지 — 실제 마커는 wiring에서. 프리뷰엔 [1]/[R1] 없음.
    out = build([_finding("blood_pressure", "경고")], "혈압")
    for fake in ("[1]", "[R1]", "[R:", "[0]"):
        assert fake not in out["block_md"]


def test_empty_findings_empty_block():
    assert build([], "혈압")["block_md"] == ""
    assert build(None, "혈압")["block_md"] == ""


# ── run() → build() 종단 연결 (경계선 ②→③) ─────────────────────

def test_run_to_build_end_to_end_neutral_and_scoped():
    rec = {"bps": 165, "bpd": 105, "bpm": 72, "fever": 36.6}
    findings = run(rec)                       # 혈압 경고 + 심박/체온 안정
    out = build(findings, "혈압이 높게 나와서요")
    # 혈압만 표면화(질의 scope), 중립 라벨, 원시값 0
    assert len(out["surfaced"]) == 1
    assert out["surfaced"][0]["signal_key"] == "blood_pressure"
    assert out["surfaced"][0]["label_user"] == "경고"
    for raw in ("165", "105"):
        assert raw not in out["block_md"]


# ── safe_block: 배선(generate_response)이 후append할 안전 블록 ────

def test_safe_block_returns_text_for_relevant_query():
    block = safe_block(run({"bps": 165, "bpd": 105}), "혈압이 높아요")
    assert block.startswith("## 📋 내 기록 참고")
    assert "의료진" in block
    for raw in ("165", "105"):
        assert raw not in block


def test_safe_block_empty_when_unrelated():
    assert safe_block(run({"bps": 165, "bpd": 105}), "오늘 날씨 어때") == ""


def test_safe_block_empty_when_no_findings():
    assert safe_block([], "혈압") == ""
    assert safe_block(None, "혈압") == ""


def test_safe_block_fail_closed_on_unsafe_content():
    # findings에 임상 라벨이 라벨로 잘못 들어와도(가상 손상) C20 백스톱이 드롭
    bad = [{"signal_key": "blood_pressure", "label_user": "고혈압 2기", "cite_doc_id": "x"}]
    # build의 _LABEL_PHRASE에 없는 라벨 → relevance_gate에서 제외되어 "" (이중 안전)
    assert safe_block(bad, "혈압") == ""


# ── 교차신호 조합 렌더 (엔진→렌더 종단) ─────────────────────────

def _band(signal, label, cite="ref.x"):
    return {"signal_key": signal, "label_user": label, "cite_doc_id": cite}


def test_cross_signal_combo_renders_when_relevant():
    findings = [_band("blood_pressure", "경고"), _band("bmi", "주의")]
    out = build(findings, "혈압이랑 체중 둘 다 걱정이에요")
    # 밴드 2개 + 교차조합 1개 표면화
    ids = [s.get("combo_id") for s in out["surfaced"] if s.get("combo_id")]
    assert "metabolic.bp_bmi" in ids
    assert "함께 살펴보면" in out["block_md"]


def test_cross_signal_combo_carries_evidence_cite():
    findings = [_band("blood_pressure", "경고"), _band("bmi", "경고")]
    out = build(findings, "혈압")
    assert "ref.metabolic.kr" in out["cite_doc_ids"]


def test_cross_signal_combo_render_passes_c20():
    # 조합 문구도 원시값·질환명 0 (C20 통과)
    findings = [_band("blood_pressure", "경고"), _band("bmi", "경고")]
    block = safe_block(findings, "혈압 체중")
    assert "함께 살펴보면" in block
    for bad in ("고혈압", "비만", "120", "140"):
        assert bad not in block


def test_cross_signal_combo_absent_below_threshold():
    # 둘 다 안정 → 조합 미발화, 밴드도 안정이라 표면화는 되지만 combo 없음
    findings = [_band("blood_pressure", "안정"), _band("bmi", "안정")]
    out = build(findings, "혈압 체중")
    assert not any(s.get("combo_id") for s in out["surfaced"])
