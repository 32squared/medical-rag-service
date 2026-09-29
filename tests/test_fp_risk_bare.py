# -*- coding: utf-8 -*-
"""FP 필터 (j) — 공용 risk_probability 의 단독 매칭어 '높습니다' 오탐 제거를 고정.

배경: 공용 analyzer 는 guidelines.json 예시를 '/'로 나눠 키프레이즈로 쓴다. 예시
"사망 위험도는 낮습니다/높습니다." 가 쪼개져 '높습니다' 단독이 HIGH 매칭어가 됐다.
실측(dev rev 00053): 값 비교(L1)·일반 양상 문장이 HIGH → 재생성 → 폴백 실패로 사과문 응답.
위험·확률 주어가 붙은 실제 위험도 제시는 반드시 보존돼야 한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _filter_guardrail_false_positives as F  # noqa: E402


def _dropped(matched, context, rule="risk_probability", severity="HIGH"):
    kept, dropped = F([{"rule_id": rule, "severity": severity,
                        "matched_text": matched, "context": context}])
    return len(dropped) == 1


# ── 실측 오탐 — 제거돼야 한다 ────────────────────────────────

def test_value_comparison_is_fp():
    assert _dropped("높습니다",
                    "...2025-03)은 참고범위 200 mg/dL 이하보다 높습니다 [내 기록][2]. 이 수치가 높다는 사실은 생활관리...")


def test_general_pattern_is_fp():
    assert _dropped("높습니다",
                    "... 전형적으로 HDL이 40대 이하로 낮고, 중성지방이 높습니다 [4]. 어떤 검사가 필요한지는 의료진이 판단합니다....")


def test_morning_value_pattern_is_fp():
    assert _dropped("높습니다",
                    "...있어요. 전형적으로 식사를 거르지 않아도 아침 수치가 높습니다. 어떤 검사가 필요한지는 의료진이 판단합니다. 보통 ...")


# ── 실제 위험도·확률 제시 — 반드시 보존 ──────────────────────

def test_dementia_risk_is_kept():
    assert not _dropped("높습니다", "1년 내 치매 진행 위험이 매우 높습니다.")


def test_cardio_risk_is_kept():
    assert not _dropped("높습니다", "심혈관 질환 발생 위험이 높습니다.")


def test_possibility_is_kept():
    assert not _dropped("높습니다", "당뇨로 진행할 가능성이 높습니다.")


def test_probability_is_kept():
    assert not _dropped("높습니다", "합병증 발생 확률이 높습니다.")


def test_mortality_is_kept():
    assert not _dropped("높습니다", "사망 위험도는 높습니다.")


# ── 범위 — 다른 규칙·다른 매칭은 건드리지 않는다 ─────────────

def test_full_example_phrase_not_affected():
    assert not _dropped("사망 위험도는 낮습니다", "사망 위험도는 낮습니다.")


def test_other_rule_not_affected():
    assert not _dropped("높습니다", "참고범위 200 이하보다 높습니다.", rule="unknown_rule")


def test_filter_disabled_by_env(monkeypatch):
    monkeypatch.setenv("RAG_GUARDRAIL_FP_FILTER", "false")
    assert not _dropped("높습니다", "참고범위 200 이하보다 높습니다.")


# ── 용량 보존 가드 — 검사 농도 단위는 용량이 아니다 ──────────
# 실측: "200 mg/dL" 이 '200 mg' 으로 잡혀 KEEP 이 강제되면서 (j) 를 포함한 어떤 오탐 규칙도
# 수치 인용 문장에 적용되지 않았다.

def test_lab_concentration_units_are_not_doses():
    from rag_engine import _FP_DOSAGE_RE
    for t in ("참고범위 200 mg/dL 이하", "크레아티닌 1.3 mg/dL", "CRP 5 mg/L", "혈당 118mg/dL"):
        assert _FP_DOSAGE_RE.search(t) is None, t


def test_real_doses_still_force_keep():
    from rag_engine import _FP_DOSAGE_RE
    for t in ("메트포르민 500mg", "500 mg 복용", "하루 1000mg/일", "2정 드세요", "하루 3회", "8시간마다"):
        assert _FP_DOSAGE_RE.search(t), t


def test_dose_in_context_still_keeps_risk_match():
    """문맥에 실제 용량이 있으면 (j) 이전에 KEEP — 처방 문맥의 위험 표현은 풀지 않는다."""
    assert not _dropped("높습니다", "메트포르민 500mg 복용 중이면 수치가 높습니다.")
