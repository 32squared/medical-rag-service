# -*- coding: utf-8 -*-
"""FP 필터 (k) — 한 글자 약물 토큰('약'·'정')이 비약물 낱말 안에서 걸리던 오탐을 고정.

배경(실측, dev rev 00055·00058·00059): '검진 결과에서 신경 써야 할 수치가 있을까요?' 답변이
CRITICAL prescription 으로 차단됐는데 로그에는 규칙 id 만 남았다. 저장된 원답을 다시 분석하니
매칭은 관리 칸의 "식사 기록을 하루 1회 요약해 적고" 의 '하루 1회'였다. 빈도 표현은 약물 문맥일
때만 용법으로 보는데, '요약'의 '약'·'일정'의 '정'이 약물 토큰으로 잡혀 KEEP 이 강제됐다.
같은 원답은 "금식 후 채혈 일정을" 로 이어져 검사 지시였다 — 공용 analyzer 는 이를 따로 잡지
못하므로 검사 토큰이 있는 빈도 매칭은 풀지 않는다.

(i) 보강: 되묻기 "현재 진단받은 질환…, 최근 지질검사 결과…가 있으신가요?" 가 '진단' 표지 때문에
CRITICAL diagnosis 로 차단됐다(rev 00059). 이미 받은 진단을 가리키는 말은 단정이 아니다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _filter_guardrail_false_positives as F  # noqa: E402


def _dropped(matched, context, rule="prescription", severity="CRITICAL"):
    kept, dropped = F([{"rule_id": rule, "severity": severity,
                        "matched_text": matched, "context": context}])
    return len(dropped) == 1


# ── 비약물 낱말 안의 '약'·'정' — 제거돼야 한다 ───────────────────

def test_summary_word_is_not_a_drug():
    assert _dropped("하루 1회", "집에서 해볼 수 있는 관리 - 2주간 식사 기록을 하루 1회 요약해 적어 보세요")


def test_normal_range_word_is_not_a_drug():
    assert _dropped("하루 3회", "정상 범위를 유지하려면 걷기를 하루 3회 10분씩 해 보세요")


def test_measurement_schedule_words_are_not_drugs():
    assert _dropped("하루 2회", "혈압 측정 일정을 정해 아침저녁 하루 2회 기록해 두면 추세를 보기 쉽습니다")


# ── 실제 약물·검사 문맥 — 반드시 보존 ────────────────────────────

def test_test_directive_context_is_kept():
    """실측 원답 그대로 — 빈도 뒤에 금식 채혈 일정이 이어진다(검사 지시)."""
    assert not _dropped("하루 1회",
                        "2주간 식사 기록을 하루 1회 요약해 적고, 저녁 9시 이후 금식 후 채혈 일정을")


def test_drug_word_is_kept():
    assert not _dropped("하루 2회", "혈압약을 하루 2회 드세요")


def test_drug_name_ending_in_jeong_is_kept():
    assert not _dropped("하루 1회", "아스피린정을 하루 1회 복용하세요")
    assert not _dropped("하루 2회", "메트포르민서방정 하루 2회 드세요")


def test_self_test_frequency_is_kept():
    assert not _dropped("하루 2회", "혈당 검사를 하루 2회 하세요")


def test_real_drug_order_sentence_kept_by_h():
    assert not _dropped("드세요", "처방받은 혈압약은 아침에 드세요")


def test_non_drug_order_sentence_dropped_by_h():
    """'정상'의 '정'이 약물로 읽혀 (h) 가 생활 권유를 처방 지시로 보던 경우."""
    assert _dropped("섭취하세요", "정상 체중을 위해 채소를 충분히 섭취하세요")


# ── (i) 진단 이력 표현 ──────────────────────────────────────────

def test_diagnosis_history_question_is_fp():
    assert _dropped("검사 결과",
                    "현재 진단받은 질환(예: 관상동맥질환 여부), 최근 지질검사 결과(LDL-C·HDL-C",
                    rule="diagnosis")


def test_history_word_does_not_hide_real_assertion():
    assert not _dropped("검사 결과", "진단받은 적은 없지만 검사 결과 당뇨병이 의심됩니다",
                        rule="diagnosis")
    assert not _dropped("검사 결과", "진단명이 없더라도 검사 결과 고혈압 소견입니다", rule="diagnosis")


# ── rev 00060 실측: '하루 0회'·간식 목록의 '시럽' ──────────────────

def test_zero_count_is_not_a_dose():
    assert _dropped("하루 0회", "단순당(탄산음료·주스·시럽·과자) 섭취를 하루 0회로 줄여 보세요 [4]. - 식후 30~60분 안에")


def test_syrup_in_snack_list_is_food():
    assert _dropped("하루 1회", "시럽·과자 같은 간식은 하루 1회 이하로 줄여 보세요")


def test_medicine_syrup_is_kept():
    assert not _dropped("하루 3회", "기침 시럽을 하루 3회 드세요")
    assert not _dropped("5ml", "해열제 시럽 5ml를 드세요")


# ── rev 00062 실측: ';' 로 이어 붙인 생활 지시와 복약 경고 ──────────────

def test_semicolon_separates_lifestyle_order_from_drug_warning():
    """뒤 절의 '처방약'(복용 금지 경고)이 앞 절의 음주 중단을 복약 지시로 만들면 안 된다."""
    assert _dropped("중단하세요", "간 취침·기상 시간을 일정하게 하고, 음주는 가능하면 중단하세요; "
                                  "남은 처방약은 임의로 복용하지 마세요 [4]")


def test_semicolon_keeps_drug_order_in_its_own_clause():
    assert not _dropped("중단하세요", "스타틴 복용은 이번 주부터 중단하세요; 대신 식단 조절을 해 보세요")
    assert not _dropped("중단하세요", "식단을 조절하고; 혈압약은 중단하세요")


# ── rev 00062 실측: 문맥 창(±30자)이 '조정'을 '정'으로 잘랐다 ───────────────

_FULL = ("**집에서 해볼 수 있는 관리**\n- 식사 조정 4주: 튀김·가공육·달달한 음료·과자·크림 소스를 "
         "하루 1회 이하로 줄이고, 생선·두부·콩·채소를 하루 2번 이상 넣어 드세요")
_CTX = ("...정 4주: 튀김·가공육·달달한 음료·과자·크림 소스를 하루 1회 이하로 줄이고, "
        "생선·두부·콩·채소를 하루 2번 이상...")


def _dropped_full(matched, context, full, rule="prescription", severity="CRITICAL"):
    kept, dropped = F([{"rule_id": rule, "severity": severity,
                        "matched_text": matched, "context": context}], full_text=full)
    return len(dropped) == 1


def test_window_cut_word_is_restored_from_full_text():
    assert not _dropped("하루 1회", _CTX)            # 창만 보면 '정'이 약물 토큰 — 보존(원문 없을 때 동작)
    assert _dropped_full("하루 1회", _CTX, _FULL)    # 원문으로 '조정' 복원 — 약물 아님


def test_window_cut_drug_name_is_still_a_drug():
    full = "두통이 잦다면 아스피린정 하루 1회 드세요. 증상이 이어지면 상담하세요."
    assert not _dropped_full("하루 1회", "...정 하루 1회 드세요. 증상이 이어지면...", full)


def test_context_not_in_full_text_is_left_as_is():
    assert not _dropped_full("하루 1회", _CTX, "전혀 다른 본문")


def test_guardrail_violations_passes_full_text():
    """실제 경로(_guardrail_violations)가 원문을 넘기는지 — 저장된 원답 구절 그대로."""
    from rag_engine import _guardrail_violations
    kept, _ = _guardrail_violations(_FULL, "총콜레스테롤이랑 중성지방 수치는 어떤가요?")
    assert not [v for v in kept if v["rule_id"] == "prescription" and v["matched_text"] == "하루 1회"]
