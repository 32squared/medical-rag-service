# -*- coding: utf-8 -*-
"""가드레일 FP 필터 (d) — 사용자가 알려준 개인 기록의 '인용'은 지시가 아니다.

배경: 프롬프트 수정으로 답변이 PHR을 활용하기 시작하자, 사용자가 스스로 알려준 복약을
되짚는 서술("현재 메트포르민서방정을 복용 중이라고 알려주셨습니다")이 공용 analyzer의
처방 규칙에 CRITICAL로 걸려 실서버에서 답변이 통째로 차단됐다(guardrail=blocked 실측).
공용 analyzer는 건드리지 않고 RAG 후처리 FP 필터에서만 해제한다.

핵심 안전선: 구체 용량·실제 명령형이 있으면 반드시 보존(KEEP)한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _filter_guardrail_false_positives as filt  # noqa: E402


def _v(matched, context, rule_id="prescription", severity="CRITICAL"):
    return [{"severity": severity, "matched_text": matched,
             "context": context, "rule_id": rule_id}]


# ── (d) 개인 기록 인용은 오탐으로 제거 ───────────────────────

def test_personal_citation_dropped():
    v = _v("메트포르민서방정을 복용",
           "현재 메트포르민서방정을 복용 중이라고 알려주셨습니다. 처방 변경은 의료진과 상의하세요.")
    kept, dropped = filt(v)
    assert kept == [] and len(dropped) == 1


def test_my_record_marker_dropped():
    v = _v("메트포르민 복용",
           "알려주신 기록의 메트포르민 복용 이력은 [내 기록] 의료진 상의가 필요합니다.")
    kept, dropped = filt(v)
    assert kept == [] and len(dropped) == 1


def test_consult_imperative_does_not_block_drop():
    # '상의하세요'의 '하세요'가 처방 명령형으로 오인돼 해제를 막던 문제
    v = _v("복용", "알려주신 기록을 보면 복용 중이시군요. 담당 의료진과 상의하세요.")
    kept, dropped = filt(v)
    assert kept == [], "진료 권유 명령형은 처방 지시가 아니다"


# ── 안전선: 실제 지시는 반드시 보존 ──────────────────────────

def test_real_dosage_directive_kept():
    v = _v("복용", "알려주신 기록 기준 메트포르민 500mg을 하루 2번 복용하세요.")
    kept, dropped = filt(v)
    assert len(kept) == 1 and dropped == [], "구체 용량은 무조건 보존"


def test_hard_imperative_kept_even_with_attribution():
    v = _v("복용", "알려주신 기록을 보니 메트포르민을 복용하세요.")
    kept, dropped = filt(v)
    assert len(kept) == 1 and dropped == [], "복용 명령형은 출처 표기가 있어도 보존"


def test_no_attribution_not_dropped_by_rule_d():
    # 개인 기록 신호가 없으면 (d)는 발동하지 않는다
    v = _v("메트포르민 복용", "메트포르민 복용 이력이 있습니다.", rule_id="unknown_rule")
    kept, dropped = filt(v)
    assert len(kept) == 1


# ── 토글·기존 경로 불변 ──────────────────────────────────────

def test_filter_disabled_keeps_everything(monkeypatch):
    monkeypatch.setenv("RAG_GUARDRAIL_FP_FILTER", "false")
    v = _v("메트포르민 복용", "알려주신 기록의 메트포르민 복용 이력입니다.")
    kept, dropped = filt(v)
    assert len(kept) == 1 and dropped == []


def test_empty_input():
    assert filt([]) == ([], [])


# ── (e) 되묻는 질문 안의 지시형 매칭 ─────────────────────────

def test_interrogative_context_dropped():
    # 실측 차단 원인: 문진 블록의 후속 질문이 처방으로 오탐됐다
    v = _v("메트포르민 포함)의 복용",
           "현재 복용 중인 약(메트포르민 포함)의 복용은 어떻게 되시나요? [1]")
    kept, dropped = filt(v)
    assert kept == [] and len(dropped) == 1


def test_interrogative_with_dosage_kept():
    v = _v("복용", "메트포르민 500mg을 하루 2번 복용하시나요?")
    kept, dropped = filt(v)
    assert len(kept) == 1, "질문이어도 구체 용량은 보존"


def test_interrogative_with_imperative_kept():
    v = _v("복용", "어떻게 되시나요? 메트포르민을 복용하세요.")
    kept, dropped = filt(v)
    assert len(kept) == 1, "질문 문맥이어도 실제 명령형은 보존"
