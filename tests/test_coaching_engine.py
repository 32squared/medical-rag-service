"""test_coaching_engine.py — 코칭 엔진(식단 문진→플랜) 결정적 테스트 (P2)."""
import pytest
import coaching_engine as ce
import coaching_compliance as cc


def test_intake_diet_three_questions():
    qs = ce.get_intake("diet")
    assert [q["id"] for q in qs] == ["eatout", "salty", "period"]
    assert all(q["options"] for q in qs)


def test_generate_plan_caution_band():
    p = ce.generate_plan("diet", {"eatout": "거의 매일", "salty": "강함", "period": "2주"}, band="주의")
    assert p["track"] == "diet"
    assert 1 <= len(p["items"]) <= 4
    assert "주의" in p["header"] and "저염" in p["header"]
    assert p["banner"] and "진료" in p["banner"]
    assert p["compliance_action"] == "pass"
    assert p["period"] == "2주"
    # 모든 항목은 KB 인용 동반
    assert all(it["cite"] for it in p["items"])


def test_generate_plan_warning_band_capped_and_soft():
    p = ce.generate_plan("diet", {"eatout": "거의 매일", "salty": "강함", "period": "1개월"}, band="경고")
    assert len(p["items"]) <= 2                       # WC-C3 강플랜 보류(soft)
    assert p["compliance_action"] == "band_capped"
    assert "경고" in p["banner"] and "진료" in p["banner"]


def test_generate_plan_stable_no_banner():
    p = ce.generate_plan("diet", {"eatout": "드뭄", "salty": "약함", "period": "2주"}, band="안정")
    assert p["banner"] is None
    assert p["compliance_action"] == "pass"
    assert len(p["items"]) >= 1


def test_generated_plan_passes_backstop():
    # 생성된 플랜 텍스트는 항상 WC-C 통과(효능표방·처방성 0)
    for band in (None, "안정", "주의", "경고"):
        p = ce.generate_plan("diet", {"eatout": "주 2~3회", "salty": "보통", "period": "2주"}, band=band)
        text = p["header"] + " " + " ".join(i["text"] for i in p["items"])
        assert cc.scan_efficacy(text) == []
        assert cc.scan_prescription(text) == []


def test_unsupported_track_raises():
    with pytest.raises(ValueError):
        ce.generate_plan("exercise", {}, band=None)
