"""test_coaching_adaptive.py — 적응형 지속 루프(§4-B) 순수 테스트 — 우선순위·무비난·비표방."""
import coaching_adaptive as ca


def test_completed_celebrates_over_all():
    assert ca.next_action(adherence=100, streak=14, days_since_last=1, completed=True) == "celebrate"


def test_gap_dominates_streak():
    # 스트릭이 높아도 공백이 있으면 재참여 우선(이탈 회복이 성취보다 먼저)
    assert ca.next_action(adherence=90, streak=10, days_since_last=2) == "reengage_gentle"
    assert ca.next_action(adherence=90, streak=10, days_since_last=5) == "reengage_replan"
    assert ca.next_action(adherence=90, streak=10, days_since_last=9) == "dormant"


def test_advance_requires_streak_and_adherence():
    assert ca.next_action(adherence=85, streak=7, days_since_last=1) == "advance"
    assert ca.next_action(adherence=60, streak=7, days_since_last=1) == "encourage"   # 실천율 부족


def test_low_adherence_simplifies():
    assert ca.next_action(adherence=30, streak=1, days_since_last=1) == "simplify"


def test_default_encourage():
    assert ca.next_action(adherence=55, streak=3, days_since_last=1) == "encourage"


def test_coach_payload_no_blame_and_reengage_flag():
    r = ca.coach(adherence=90, streak=5, days_since_last=5)
    assert r["action"] == "reengage_replan" and r["no_blame"] is True and r["reengage"] is True
    assert "죄책감" in r["message"]
    enc = ca.coach(adherence=55, streak=3)
    assert enc["reengage"] is False


def test_messages_are_behavior_only_no_health_claims():
    # 모든 메시지에 효능/건강결과/진단 표현이 없어야 함(WC-C)
    banned = ["좋아져", "낫", "치료", "효과", "혈압", "혈당", "완치", "예방"]
    for a in ["celebrate", "advance", "encourage", "simplify",
              "reengage_gentle", "reengage_replan", "dormant"]:
        msg = ca.message(a, streak=5)
        assert not any(b in msg for b in banned), f"{a}: {msg}"


def test_advance_interpolates_streak():
    assert "7일" in ca.message("advance", streak=7)
