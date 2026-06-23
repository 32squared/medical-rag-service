"""test_anticipatory_engine.py — 선제 트리거 엔진(G1) 순수 테스트."""
import anticipatory_engine as ae


def test_emergency_top_priority():
    t = ae.top({"emergency": True, "band": "주의", "warning_days": 5})
    assert t["rule"] == "R0" and t["priority"] == 0 and t["referral"] == "emergency"


def test_warning_band_must_attend_with_disclaimer():
    t = ae.top({"band": "경고", "warning_days": 3})
    assert t["kind"] == "must_attend"
    assert t["referral"] == "hospital"
    assert "진단" in t["note"]


def test_caution_band_needs_streak():
    assert ae.top({"band": "주의", "warning_days": 1}) is None      # 1일은 미표면화
    t = ae.top({"band": "주의", "warning_days": 3})
    assert t and t["rule"] == "R1b"


def test_reminders():
    assert any(c["rule"] == "R2" for c in ae.evaluate({"band": "안정", "med_due": True}))
    assert any(c["rule"] == "R2c" for c in ae.evaluate({"band": "안정", "checkup_d": 5}))
    assert ae.evaluate({"band": "안정", "checkup_d": 30}) == []     # 멀면 미표면화


def test_stable_is_quiet():
    assert ae.top({"band": "안정"}) is None
    assert ae.top({}) is None


def test_coaching_reengage():
    t = ae.top({"band": "안정", "coaching_missed_days": 4})
    assert t["rule"] == "R4" and t["kind"] == "nudge"


def test_priority_order():
    cands = ae.evaluate({"emergency": True, "band": "경고", "warning_days": 3, "med_due": True})
    assert [c["priority"] for c in cands] == sorted(c["priority"] for c in cands)
    assert cands[0]["rule"] == "R0"


def test_anticipated_questions():
    qs = ae.anticipated_questions({"band": "주의", "trend": "악화"})
    assert 1 <= len(qs) <= 3
    assert ae.anticipated_questions({"band": "안정"}) == []


def test_should_surface_honors_dismissed_but_not_emergency():
    sig = {"band": "경고", "warning_days": 3, "med_due": True}
    # R1 무시 → R2(복약)로 내려감
    assert ae.should_surface(sig, dismissed_rules=["R1"])["rule"] == "R2"
    # 응급은 무시 불가
    em = {"emergency": True}
    assert ae.should_surface(em, dismissed_rules=["R0"])["rule"] == "R0"
