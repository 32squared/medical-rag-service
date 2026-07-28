"""test_coaching_compliance.py — WC-C 백스톱(효능표방·처방성) 순수 테스트 (P2)."""
import pytest
import coaching_compliance as cc


def test_scan_efficacy_catches_cure_claims():
    assert cc.scan_efficacy("이 식단이 고혈압을 낫게 합니다")
    assert cc.scan_efficacy("혈압을 낮춰줍니다")
    assert cc.scan_efficacy("약 없이도 관리됩니다")
    assert cc.scan_efficacy("당뇨를 완치할 수 있어요")


def test_scan_efficacy_clean_passes():
    assert cc.scan_efficacy("국물은 절반만 남기기") == []
    assert cc.scan_efficacy("끼니마다 채소 한 접시 더하기") == []


def test_scan_prescription_catches_dosage():
    assert cc.scan_prescription("나트륨을 1500mg로 제한하세요")
    assert cc.scan_prescription("목표심박 85% 까지 올리세요")


def test_scan_prescription_clean_passes():
    assert cc.scan_prescription("간을 평소보다 싱겁게 하기") == []


def test_check_plan_blocks_efficacy():
    r = cc.check_plan("저염 식단이 고혈압을 낫게 합니다")
    assert r["ok"] is False and r["action"] == "blocked"


def test_check_plan_softens_prescription():
    r = cc.check_plan("나트륨을 1500mg로 제한")
    assert r["ok"] is False and r["action"] == "softened"


def test_check_plan_pass_clean():
    r = cc.check_plan("국물 반 남기기 · 채소 한 접시 더하기", band="주의")
    assert r["ok"] is True and r["action"] == "pass"


def test_assert_plan_safe_raises():
    with pytest.raises(ValueError):
        cc.assert_plan_safe("고혈압을 낫게 하는 식단")
    cc.assert_plan_safe("싱겁게 먹고 채소 늘리기")   # 정상=예외 없음
