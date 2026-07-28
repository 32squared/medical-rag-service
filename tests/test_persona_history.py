"""
페르소나 종단 데이터 생성기 — persona_history.

매일 측정 바이탈(7~180일)·검진 10년·처방 5년이 결정적으로 생성되고,
마지막 측정이 authored 현재값과 일치(엔진 일관성)하는지 검증한다.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import persona_history as ph  # noqa: E402
import persona_test_server as pts  # noqa: E402

ANCHOR = date(2026, 6, 21)


def _p(pid):
    return next(x for x in pts.load_personas()["personas"] if x["id"] == pid)


def test_window_days_by_profile():
    assert ph.window_days(_p("fever_adult")) == 10        # 급성
    assert ph.window_days(_p("hypertension_senior")) == 180  # 만성
    assert ph.window_days(_p("bp_rising_trend")) == 120   # history override


def test_vitals_series_daily_and_anchored():
    p = _p("hypertension_senior")
    s = ph.generate_vitals_series(p)
    assert len(s) == 180
    assert s[-1]["create_date"][:10] == "2026-06-21"      # 최근 = 기준일
    assert s[0]["create_date"][:10] == "2025-12-24"       # 180일 전
    # 마지막 측정 = authored 현재값(엔진 일관성)
    assert s[-1]["bps"] == p["vitals"][-1]["bps"]
    # 매일 1건(중복 날짜 없음)
    days = [r["create_date"][:10] for r in s]
    assert len(set(days)) == 180


def test_vitals_series_deterministic():
    p = _p("diabetes_followup")
    assert ph.generate_vitals_series(p) == ph.generate_vitals_series(p)


def test_rising_trend_increases():
    p = _p("bp_rising_trend")
    s = ph.generate_vitals_series(p)
    assert s[0]["bps"] < s[-1]["bps"]                     # 과거 < 현재
    assert s[-1]["bps"] == 156


def test_checkups_ten_years():
    chk = ph.generate_checkups(_p("hypertension_senior"))
    assert len(chk) == 10
    assert chk[0]["year"] == 2017 and chk[-1]["year"] == 2026
    assert "당화혈색소" not in chk[0]                       # 비당뇨


def test_checkups_diabetic_has_hba1c_and_rising_glucose():
    chk = ph.generate_checkups(_p("diabetes_followup"))
    assert "당화혈색소" in chk[0]
    assert chk[0]["공복혈당"] < chk[-1]["공복혈당"]          # 악화 추세


def test_prescriptions_five_years():
    rx = ph.generate_prescriptions(_p("hypertension_senior"))
    years = {int(v["date"][:4]) for v in rx}
    assert min(years) == 2022 and max(years) <= 2026 and len(years) >= 4  # 5년 범위
    assert all(v["date"] <= ANCHOR.isoformat() for v in rx)  # 미래 진료 없음
    assert all(v["dept"] == "순환기내과" for v in rx)
    assert any("암로디핀" in (v["drug"] or "") for v in rx)
    assert rx == sorted(rx, key=lambda x: x["date"])         # 날짜 정렬


def test_acute_persona_few_visits():
    rx = ph.generate_prescriptions(_p("fever_adult"))      # 비만성
    assert len(rx) <= 10 and all(v["drug"] is None for v in rx)


def test_serializable():
    import json
    for p in pts.load_personas()["personas"]:
        json.dumps(ph.generate_vitals_series(p))
        json.dumps(ph.generate_checkups(p))
        json.dumps(ph.generate_prescriptions(p))
