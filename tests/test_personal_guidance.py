"""
밴드별 행동 안내(navigation·안전) — personal_context._GUIDANCE.

블록이 밴드에 따라 다른 다음-행동을 덧붙이되(경고=적신호→응급실, 주의=재측정/관리),
원시값·질환명 0(C20/C21)이고 119 등 2자리 숫자가 없는지 검증한다.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as vr  # noqa: E402
import personal_context as pc  # noqa: E402
from personalization_safety import scan_personal_block  # noqa: E402


def _block(vals, q):
    return pc.safe_block(vr.run(vals), q)


def test_warning_block_has_redflag_guidance():
    blk = _block({"bps": 152, "bpd": 96}, "혈압 낮추려면 뭘 해야 하나요?")
    assert "응급실" in blk           # 적신호 안내
    assert "진료" in blk
    assert scan_personal_block(blk)["safe"]   # C20 통과


def test_caution_block_has_navigation_guidance():
    blk = _block({"bps": 134, "bpd": 85}, "혈압이 높다고 나왔어요")
    assert ("재서" in blk) or ("측정 기록" in blk)   # 재측정·기록 지참
    assert scan_personal_block(blk)["safe"]


def test_guidance_has_no_raw_numbers_or_emergency_digits():
    # 모든 밴드 안내에 2자리+ 숫자(119·38 등)가 없어야 한다
    for sig, bands in pc._GUIDANCE.items():
        for label, text in bands.items():
            assert not re.search(r"\d{2,}", text), f"{sig}/{label}에 2자리 숫자"


def test_stable_band_gets_no_guidance():
    # 안정 라벨(건강)에는 행동 안내가 붙지 않는다(과의료화 방지)
    blk = _block({"bps": 118, "bpd": 76}, "두통이 있어요")
    assert "응급실" not in blk and "재서" not in blk


def test_temperature_warning_guidance():
    blk = _block({"fever": 39.1}, "열이 39도까지 나요")
    assert "응급실" in blk and scan_personal_block(blk)["safe"]
