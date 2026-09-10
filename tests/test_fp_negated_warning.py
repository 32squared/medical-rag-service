# -*- coding: utf-8 -*-
"""FP 필터 (f)(g) — 금지 경고문과 비약물 빈도 표현이 처방으로 오탐되지 않게 고정.

배경(실측, dev rev 00048): persly-safe 프로필 8건 중 6건이 prescription 룰로 차단됐다.
매칭 문구는 전부 오탐이었다.
  «남은 처방약을 임의로 복용하지 마세요»  → 복약을 '금지'하는 안전 경고문
  «하루 3회» (중립자세 연습을 1회 5분, 하루 3회) → 약물이 없는 운동 빈도
(f)는 매칭 문구 '안'의 부정을, (g)는 약물 토큰 없는 빈도 단독 매칭을 제거한다.
실제 처방 지시(용량·약물+지시)는 보존돼야 하므로 그 반대 케이스도 함께 잠근다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _filter_guardrail_false_positives as F  # noqa: E402


def _run(matched, context, rule="prescription", severity="CRITICAL"):
    kept, dropped = F([{"rule_id": rule, "severity": severity,
                        "matched_text": matched, "context": context}])
    return len(dropped) == 1


# ── (f) 매칭 문구 안에서 행위가 부정된 경고문 ────────────────

def test_prescription_ban_warning_is_fp():
    assert _run("처방약을 임의로 복용하지 마세요",
                "약 사용은 의료진·약사와 상담이 필요합니다. "
                "남은 처방약을 임의로 복용하지 마세요 [4].")


def test_painkiller_ban_warning_is_fp():
    assert _run("진통제를 임의로 복용하지 마세요. 약 사용",
                "- 약 사용 주의: 남은 처방약이나 진통제를 임의로 복용하지 마세요. "
                "약 사용은 의료진·약사와 상담이 필요합니다 [4].")


def test_negation_followed_by_directive_is_kept():
    """…마시고 대신 …하세요 는 실제 지시다 — 부정만 보고 놓아주면 안 된다."""
    assert not _run("복용하지 마시고 대신 아침에 복용하세요",
                    "저녁에는 복용하지 마시고 대신 아침에 복용하세요.")


# ── (g) 약물 없는 빈도 표현 ──────────────────────────────────

def test_exercise_frequency_is_fp():
    assert _run("하루 3회",
                "허리를 곧게 세우는 중립자세 연습을 1회 5분, 하루 3회 해보세요 [1].")


def test_stretching_frequency_is_fp():
    assert _run("하루 2회", "가벼운 스트레칭을 하루 2회 해보세요.")


def test_drug_frequency_is_kept():
    """같은 «하루 3회»라도 약물 맥락이면 용법이다 — 보존."""
    assert not _run("하루 3회", "이 약을 하루 3회 드세요.")


def test_drug_frequency_with_directive_is_kept():
    assert not _run("하루 3회 복용하세요", "이 약을 하루 3회 복용하세요.")


# ── 실제 처방 지시는 계속 보존 ───────────────────────────────

def test_real_dose_directive_is_kept():
    assert not _run("메트포르민 500mg으로 올리세요",
                    "혈당이 높으니 메트포르민 500mg으로 올리세요.")


def test_hourly_interval_with_drug_is_kept():
    assert not _run("8시간마다", "이 약을 8시간마다 복용하세요.")


def test_filter_disabled_by_env(monkeypatch):
    """킬 스위치가 살아 있어야 한다 — 필터 자체를 끄면 아무것도 제거하지 않는다."""
    monkeypatch.setenv("RAG_GUARDRAIL_FP_FILTER", "false")
    assert not _run("하루 2회", "가벼운 스트레칭을 하루 2회 해보세요.")
