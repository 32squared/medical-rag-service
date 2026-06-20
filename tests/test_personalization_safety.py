"""personalization_safety 단위 테스트 — C20 차단 스캐너 + C21 I2 명사 게이트."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from personal_context import build
from personalization_safety import (
    assert_personal_block_safe,
    find_clinical_labels,
    scan_personal_block,
)
from vital_rules import run


# ── C21: 명사구 진단·병기 라벨 (종결어미 regex의 구멍 보강) ───────

def test_c21_catches_noun_phrase_diagnoses():
    # citation_verifier 종결어미 정규식이 통과시키는 명사구들
    assert find_clinical_labels("최근 기록은 고혈압 1기에 해당합니다")
    assert find_clinical_labels("당뇨병 기준에 해당하는 수치가 확인됩니다")  # '~입니다' 아닌 명사구
    assert find_clinical_labels("BMI상 2단계 비만 구간")
    assert find_clinical_labels("공복혈당장애 범위")
    assert find_clinical_labels("고혈압전단계")


def test_c21_tolerates_spacing_variants():
    assert find_clinical_labels("고혈압2기")
    assert find_clinical_labels("3 단계 비만")


def test_c21_does_not_flag_neutral_text():
    # 중립 라벨 문구는 진단 라벨 아님
    assert find_clinical_labels("관리가 권장되는 구간으로 확인됩니다") == []
    assert find_clinical_labels("기준을 벗어난 구간으로, 의료진 확인이 권장됩니다") == []
    assert find_clinical_labels("최근 측정된 혈압은(는) 특이소견이 보이지 않습니다") == []


# ── C20: 개인 블록 백스톱 (원시값·질환명·임상라벨 0) ─────────────

def test_c20_flags_raw_values():
    r = scan_personal_block("최근 혈압은 165/105로 측정되었습니다")
    assert not r["safe"]
    assert "raw_value" in r["violations"]


def test_c20_flags_disease_noun_and_clinical_label():
    r = scan_personal_block("귀하는 고혈압 2기로 보입니다")
    assert not r["safe"]
    assert any(v.startswith("disease_noun:") for v in r["violations"])
    assert any(v.startswith("clinical_label:") for v in r["violations"])


def test_c20_passes_clean_neutral_block():
    clean = ("## 📋 내 기록 참고\n"
             "- 최근 측정된 혈압은(는) 기준을 벗어난 구간으로, 의료진 확인이 권장됩니다.\n\n"
             "측정값의 해석과 진단은 의료진과 상담하세요.")
    r = scan_personal_block(clean)
    assert r["safe"], r["violations"]


def test_c20_empty_is_safe():
    assert scan_personal_block("")["safe"]
    assert scan_personal_block(None)["safe"]


def test_assert_raises_on_violation_and_passes_clean():
    with pytest.raises(ValueError):
        assert_personal_block_safe("혈압 165 고혈압 2기")
    # 깨끗하면 예외 없음
    assert_personal_block_safe("관리가 권장되는 구간으로 확인됩니다")


# ── 핵심 통합: build() 출력은 항상 게이트를 통과(render ↔ gate 정합) ──

def test_build_output_always_passes_gate():
    """다양한 finding 조합에서 personal_context.build()의 block_md가 C20을 통과해야 함.
    (render가 라벨만 생성한다는 불변식과 gate가 일치하는지)."""
    queries_findings = [
        ("혈압이 높아요", {"bps": 165, "bpd": 105}),     # 경고
        ("혈당이 걱정돼요", {"fever": 36.6}),             # 무관 → 빈 블록
        ("체중이 늘었는데 혈압도", {"bps": 145, "bpd": 92}),
        ("산소포화도 낮을 때 호흡곤란", {"spo2": 92}),
    ]
    for query, rec in queries_findings:
        out = build(run(rec), query)
        res = scan_personal_block(out["block_md"])
        assert res["safe"], f"{query}: {res['violations']} / block={out['block_md']!r}"
