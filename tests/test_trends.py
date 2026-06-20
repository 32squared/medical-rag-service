"""
추세 표면화 — vital_rules.run_trends + personal_context 결합 (정본 14 §6.2).

다회 측정 시계열 → 신호별 중립 추세 finding(지속상승/저하/불안정만, 안정유지·표본부족 미발화),
그리고 personal_context가 관련 질의에서만 '흐름' 노트로 결합하는지(원시값 미노출)를 검증한다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as vr  # noqa: E402
import personal_context as pc  # noqa: E402


def _recs(bps_series):
    return [{"bps": v, "bpd": 80} for v in bps_series]


# ── 단위: run_trends ─────────────────────────────────────────
def test_rising_trend_surfaces():
    out = vr.run_trends(_recs([138, 144, 150, 156]))
    bp = [f for f in out if f["signal_key"] == "blood_pressure"]
    assert bp and bp[0]["trend"] == vr.TREND_RISING
    assert bp[0]["kind"] == "trend" and bp[0]["label_user"] is None
    assert "점차 높아지는 흐름" in bp[0]["sentence"]
    # 원시값 미노출
    for raw in ("138", "156"):
        assert raw not in bp[0]["sentence"]


def test_falling_trend():
    out = vr.run_trends([{"spo2": v} for v in [98, 95, 93, 91]])
    sp = [f for f in out if f["signal_key"] == "spo2"]
    assert sp and sp[0]["trend"] == vr.TREND_FALLING


def test_stable_not_surfaced():
    # 변동 거의 없음 → 안정유지 → 미발화
    assert vr.run_trends(_recs([120, 121, 120, 119])) == []


def test_insufficient_samples():
    assert vr.run_trends(_recs([130, 150])) == []   # n<3


# ── 결합: personal_context ───────────────────────────────────
def test_trend_surfaces_on_related_query():
    findings = vr.run_trends(_recs([138, 144, 150, 156]))
    blk = pc.safe_block(findings, "요즘 혈압이 점점 오르는 것 같아요")
    assert blk and "혈압" in blk and "흐름" in blk


def test_trend_suppressed_on_unrelated_query():
    findings = vr.run_trends(_recs([138, 144, 150, 156]))
    assert pc.safe_block(findings, "감기약 먹어도 되나요?") == ""


# ── 페르소나 미리보기 통합 ───────────────────────────────────
def test_persona_preview_includes_trend():
    import persona_test_server as pts
    data = pts.load_personas()
    p = next(x for x in data["personas"] if x["id"] == "bp_rising_trend")
    out = pts.compute_preview(p, "혈압이 계속 올라가는데 괜찮을까요?")
    # 최근값 밴드(경고) + 추세 노트가 함께
    assert any(f["signal"] == "blood_pressure" for f in out["findings"])
    assert "흐름" in out["safe_block"]
