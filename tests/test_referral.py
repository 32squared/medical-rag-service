"""test_referral.py — 시설 안내(§5.8) 순수 테스트 — 중립성·응급 우선."""
import referral as rf


def test_emergency_urgent_egen():
    r = rf.referral(intent="emergency")
    assert r["urgent"] is True
    assert "119" in r["message"]
    assert r["links"][0]["url"] == "https://www.e-gen.or.kr"
    assert rf.referral(band="응급")["urgent"] is True


def test_normal_neutral_directories():
    r = rf.referral(band="주의")
    assert r["urgent"] is False
    assert "추천이 아닌" in r["message"]
    assert rf.is_neutral(r["links"]) is True
    assert len(r["links"]) == 2     # 병원 + 약국


def test_warning_band_prioritizes_care():
    r = rf.referral(band="경고")
    assert "진료를 우선" in r["message"]


def test_kind_filters():
    assert rf.referral(kind="pharmacy")["links"][0]["url"] == "https://www.health.kr"
    assert rf.referral(kind="hospital")["links"][0]["url"] == "https://www.hira.or.kr"


def test_department_hint_not_assertive():
    h = rf.department_hint("혈압이 높게 나왔어요")
    assert "내과" in h and "최종 판단은 의료진" in h
    assert rf.department_hint("그냥 궁금해요") is None


def test_neutrality_rejects_private():
    assert rf.is_neutral([{"name": "OO병원", "url": "https://private-clinic.example"}]) is False
    assert rf.is_neutral([rf.PUBLIC["hospital"]]) is True
