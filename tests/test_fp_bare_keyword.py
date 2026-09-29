# -*- coding: utf-8 -*-
"""FP 필터 (i) — 공용 diagnosis 키워드 '검사 결과' 단독 매칭 오탐 제거를 고정.

배경(실측, dev rev 00051): 공용 violation_rules.json 의 diagnosis.keywords 에 '검사 결과'가
있어, 금지 4항목(LDL·eGFR·골밀도·요단백) 답변이 해석을 의료진에게 넘기는 문장에서 CRITICAL
차단됐다(재현 3회 중 2회). 진단 단정 문형은 같은 규칙의 별도 패턴이 따로 잡으므로 여기서는
키워드 단독 매칭만 본다. 진단 단정이 붙은 문장은 반드시 보존돼야 한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _filter_guardrail_false_positives as F  # noqa: E402


def _dropped(matched, context, rule="diagnosis", severity="CRITICAL"):
    kept, dropped = F([{"rule_id": rule, "severity": severity,
                        "matched_text": matched, "context": context}])
    return len(dropped) == 1


# ── 실측 오탐 — 제거돼야 한다 ────────────────────────────────

def test_prior_result_as_interpretation_context_is_fp():
    assert _dropped("검사 결과",
                    "골밀도: 측정 부위(요추/대퇴), 이전 검사 결과 유무, 낙상 경험, 가족력 등은 해석에 참고가 됩니다")


def test_repeat_result_with_deferral_is_fp():
    assert _dropped("검사 결과",
                    "단일 검사로 확정적인 해석을 하기보다, 채뇨 조건·반복 검사 결과·동반 소견을 "
                    "함께 보고 의료진이 판단하도록 안내됩니다")


# ── 진단 단정 — 반드시 보존 ──────────────────────────────────

def test_assertive_ending_right_after_keyword_is_kept():
    assert not _dropped("검사 결과", "검사 결과 암입니다.")


def test_diagnosis_word_is_kept():
    assert not _dropped("검사 결과", "검사 결과 당뇨병으로 진단됩니다.")


def test_suspicion_is_kept():
    assert not _dropped("검사 결과", "검사 결과 빈혈이 의심됩니다.")


def test_abnormal_finding_with_need_is_kept():
    assert not _dropped("검사 결과", "검사 결과 이상이 있어 추가 검사가 필요합니다.")


def test_finding_assertion_is_kept():
    assert not _dropped("검사 결과", "검사 결과상 고혈압 소견입니다.")


# ── 범위 — 다른 규칙·다른 매칭은 건드리지 않는다 ─────────────

def test_other_rule_not_affected():
    assert not _dropped("검사 결과",
                        "이전 검사 결과 유무, 낙상 경험 등은 해석에 참고가 됩니다",
                        rule="unknown_rule")


def test_pattern_match_not_affected():
    """키워드가 아닌 패턴 매칭(더 긴 매칭 문구)은 (i) 대상이 아니다."""
    assert not _dropped("검사 결과 간 기능 이상으로 확인됩니다",
                        "검사 결과 간 기능 이상으로 확인됩니다.")


def test_filter_disabled_by_env(monkeypatch):
    monkeypatch.setenv("RAG_GUARDRAIL_FP_FILTER", "false")
    assert not _dropped("검사 결과",
                        "이전 검사 결과 유무, 낙상 경험, 가족력 등은 해석에 참고가 됩니다")
