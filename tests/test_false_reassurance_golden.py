"""거짓안심(false reassurance) 골든셋 — 비평가 요구 안전 회귀 (정본 11 §6·12 §9·14).

거짓안심 = 위험 신호를 '안정'으로 오라벨하거나, 의료기기 아닌 측정을 임상 안심으로 주는 것.
이전엔 "거짓안심률 0"이 측정 정의 없는 KPI였다 — 본 골든셋이 각 벡터를 회귀 케이스로 박제해
정의·측정한다. 안심 비대칭 원칙: 경고는 민감하게, 안심은 보수적으로(미시드 구간은 no_match).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_context import build
from vital_rules import lookup_band, run


def _bp(s, d):
    return {"systolic": s, "diastolic": d}


# ── Vector 1: 백의/가면 고혈압 — 가정혈압 정상 tier 미시드 → 안심 강제 안 함 ──
def test_v1_white_coat_home_bp_no_false_reassurance():
    r = lookup_band("blood_pressure", _bp(130, 82), context="home", locale="KR")
    assert r["match"] == "no_match"
    assert r["label_user"] != "안정"   # 역치 미만이어도 '안정' 단정 안 함(거짓안심 비대칭)


# ── Vector 2: 약 복용 중 경계 혈압 — 130/80 → 주의(안정 아님) ──
def test_v2_borderline_bp_not_falsely_stable():
    # 복약으로 조절된 듯한 130/80도 경계구간 → 주의. '안정'으로 안심시키지 않음.
    assert lookup_band("blood_pressure", _bp(130, 80), locale="KR")["label_user"] == "주의"


# ── Vector 3: 워치 SpO2 96% — 어두운 피부 과대측정(FDA) → wellness deny ──
def test_v3_watch_spo2_denied_not_reassured():
    r = lookup_band("spo2", 96, device_grade="wellness")
    assert r["match"] == "denied"
    assert r["label_user"] is None      # 웰니스 기기 SpO2를 '안정'으로 안심시키지 않음


# ── Vector 4: HRV 노이즈 — 공인 임상 밴드 없음 → no_match(라벨 안 줌) ──
def test_v4_hrv_has_no_clinical_band():
    r = lookup_band("hrv", 30)
    assert r["match"] == "no_match"
    assert r["label_user"] is None


# ── Vector 5: 위험값은 반드시 경고/주의로 표면화(under-label 거짓안심 0) ──
def test_v5_dangerous_values_surface_as_warning():
    assert lookup_band("blood_pressure", _bp(165, 105), locale="KR")["label_user"] == "경고"
    assert lookup_band("fasting_glucose", 200, locale="KR")["label_user"] == "경고"
    assert lookup_band("hba1c", 7.5, locale="KR")["label_user"] == "경고"
    assert lookup_band("spo2", 88)["label_user"] == "경고"        # 의료기기 등급
    assert lookup_band("body_temperature", 39.0, population="adult")["label_user"] == "경고"


# ── Vector 6: 종단 — 위험 혈압 답변 블록에 '안정' 문구 없음, 경고 문구 있음 ──
def test_v6_end_to_end_no_stable_phrase_for_warning():
    out = build(run({"bps": 165, "bpd": 105}), "혈압이 높게 나와서 걱정이에요")
    assert "특이소견이 보이지 않습니다" not in out["block_md"]   # 안정 문구 부재
    assert "기준을 벗어난 구간" in out["block_md"]                # 경고 문구 존재
    assert "의료진" in out["block_md"]


# ── Vector 7: 무관 질의 — 개인화 과노출 0(블록 빔) ──
def test_v7_unrelated_query_no_personal_exposure():
    assert build(run({"bps": 165, "bpd": 105}), "오늘 점심 메뉴 추천")["block_md"] == ""


# ── Vector 8: 소아 발열 — 고위험 미구조화 → 안심 라벨 안 줌(fail-closed) ──
def test_v8_pediatric_fever_no_false_reassurance():
    r = lookup_band("body_temperature", 38.5, population="child")
    assert r["match"] == "no_match"
    assert r["label_user"] is None


# ── Vector 9: 안심(안정)은 명확한 정상에서만 — 경계 근처는 안심 안 함 ──
def test_v9_stable_only_for_clear_normal():
    assert lookup_band("blood_pressure", _bp(110, 70), locale="KR")["label_user"] == "안정"
    # 경계 바로 위(수축기 120)는 안정 아님 — 정상혈압은 <120(미포함)
    assert lookup_band("blood_pressure", _bp(120, 70), locale="KR")["label_user"] != "안정"
