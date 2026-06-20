"""
교차신호 live — 혈압+BMI 대사 묶음 (정본 14 §6 C9 / I9 화이트리스트).

BMI를 개인화 입력에 추가했을 때, 혈압 경고 + BMI 주의가 함께면 화이트리스트 조합
(metabolic.bp_bmi)이 '함께 살펴보기' 노트로 결합되는지(출처 첨부·진단 아님), 그리고
관련 질의에서만 표면화되는지를 검증한다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as vr  # noqa: E402
import personal_context as pc  # noqa: E402


def test_bmi_band_via_run():
    f = vr.run({"bmi": 27.4})
    bmi = [x for x in f if x["signal_key"] == "bmi"]
    assert bmi and bmi[0]["label_user"] == "주의"
    # 정상 BMI는 안정
    assert vr.run({"bmi": 21.0})[0]["label_user"] == "안정"


def test_cross_signal_fires_on_bp_plus_bmi():
    findings = vr.run({"bps": 150, "bpd": 95, "bmi": 27.4})
    labels = {f["signal_key"]: f["label_user"] for f in findings}
    assert labels.get("blood_pressure") == "경고" and labels.get("bmi") == "주의"
    combos = vr.match_cross_signals(findings)
    assert any(c["combo_id"] == "metabolic.bp_bmi" for c in combos)


def test_cross_signal_not_fired_when_only_one_signal():
    # 혈압만 경고, BMI 정상 → 조합 미발화(fail-closed)
    findings = vr.run({"bps": 150, "bpd": 95, "bmi": 21.0})
    assert vr.match_cross_signals(findings) == []


def test_cross_signal_surfaced_in_block():
    findings = vr.run({"bps": 150, "bpd": 95, "bmi": 27.4})
    blk = pc.safe_block(findings, "혈압이랑 체중 둘 다 관리하려면 어떻게 해요?")
    assert blk
    assert "함께 살펴보" in blk           # 교차신호 결합 노트
    assert "혈압" in blk and "체질량지수" in blk
    # 원시값 미노출
    for raw in ("150", "95", "27"):
        assert raw not in blk


def test_cross_signal_suppressed_on_unrelated_query():
    findings = vr.run({"bps": 150, "bpd": 95, "bmi": 27.4})
    # 혈압·체중 scope를 건드리지 않는 질의 → 조합 미표면화
    assert pc.safe_block(findings, "감기약 먹어도 되나요?") == ""


def test_persona_preview_metabolic_combo():
    import persona_test_server as pts
    data = pts.load_personas()
    p = next(x for x in data["personas"] if x["id"] == "metabolic_multi")
    out = pts.compute_preview(p, "혈압이랑 체중 둘 다 관리하려면?")
    sigs = {f["signal"] for f in out["findings"]}
    assert "blood_pressure" in sigs and "bmi" in sigs
    assert "함께 살펴보" in out["safe_block"]
