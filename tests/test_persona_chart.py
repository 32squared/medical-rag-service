"""
페르소나 측정 그래프 스펙 — persona_test_server.build_chart.

신호별 시계열(점=측정값, 밴드=vital_rules 권위 분류, 구간=참고)이 올바로 구성되는지,
다회 측정(추세)·인구집단(소아) 반영을 검증한다. 원시값은 점 좌표로만 노출.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import persona_test_server as pts  # noqa: E402


def _persona(pid):
    return next(p for p in pts.load_personas()["personas"] if p["id"] == pid)


def _series(chart, signal):
    return next((s for s in chart["series"] if s["signal"] == signal), None)


def test_trend_persona_has_four_bp_points():
    chart = pts.build_chart(_persona("bp_rising_trend"))
    bp = _series(chart, "blood_pressure")
    assert bp and len(bp["points"]) == 4
    assert [p["v"] for p in bp["points"]] == [138, 144, 150, 156]   # 점=수축기
    assert bp["points"][-1]["band"] == "경고"
    assert len(bp["second"]) == 4                                   # 이완기 보조선
    assert bp["zones"]                                              # 참고 구간


def test_hypertension_bp_warning_and_spo2_stable():
    chart = pts.build_chart(_persona("hypertension_senior"))
    assert _series(chart, "blood_pressure")["points"][-1]["band"] == "경고"
    assert _series(chart, "spo2")["points"][-1]["band"] == "안정"


def test_respiratory_signals_present():
    chart = pts.build_chart(_persona("respiratory_lowspo2"))
    assert _series(chart, "spo2")["points"][-1]["band"] == "주의"
    assert _series(chart, "body_temperature") is not None


def test_pediatric_value_plotted_without_adult_band():
    # 소아: 값은 점으로 찍히되, 성인 밴드로 분류하지 않음(band None)
    chart = pts.build_chart(_persona("pediatric_guardian"))
    temp = _series(chart, "body_temperature")
    assert temp and temp["points"][-1]["v"] == 38.5
    assert temp["points"][-1]["band"] is None


def test_chart_serializable():
    import json
    for p in pts.load_personas()["personas"]:
        json.dumps(pts.build_chart(p))   # 직렬화 가능(서버 응답)


def test_stress_plotted_without_band():
    # 무밴드 측정(스트레스)도 그래프에 포함되되 분류(색)는 없음
    chart = pts.build_chart(_persona("anxiety_palpitation"))  # stress 88
    st = _series(chart, "stress")
    assert st and st["points"][-1]["v"] == 88
    assert st["points"][-1]["band"] is None and st["zones"] == []


def test_profile_full_data():
    prof = pts.build_profile(_persona("hypertension_senior"))
    labels = {m["label"]: m["value"] for m in prof["measures"]}
    assert labels.get("수축기 혈압") == 152 and labels.get("이완기 혈압") == 96
    phr = {r["label"]: r["value"] for r in prof["phr"]}
    assert "복약" in phr
    assert prof["readings"] == 1


def test_profile_phr_parsed():
    prof = pts.build_profile(_persona("diabetes_followup"))
    phr = {r["label"]: r["value"] for r in prof["phr"]}
    assert phr.get("당화혈색소") == "7.2"
    assert "type2_diabetes" in phr.get("진단 이력", "")


def test_profile_serializable():
    import json
    for p in pts.load_personas()["personas"]:
        json.dumps(pts.build_profile(p))
