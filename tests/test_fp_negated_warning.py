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


# ── (h) prescription = 약물 + 비상담 명령형이 한 문장에 ──────

def test_causal_explanation_is_fp():
    """"진통제 잦은 복용이 통증 역치를 흔듭니다" — 명령형 없는 인과 설명."""
    assert _run("진통제 잦은 복용이나 카페인 과다·중단",
                "약물·카페인 사용 패턴 변화: 진통제 잦은 복용이나 카페인 과다·중단이 "
                "통증 역치를 흔듭니다. 아침 기상 시 더 심하고")


def test_consult_referral_is_fp():
    """진료에서 논의하라는 권유는 처방 지시가 아니다."""
    assert _run("진통제 사용",
                "병용 가능성을 의료진에게 확인하세요. 다음 진료에서 "
                "\u201c진통제 사용 계획과 위장 증상 악화 가능성\u201d을 함께 논의해 보세요.")


def test_non_drug_stop_directive_is_fp():
    """"음주는 중단하세요"는 생활습관 권고다."""
    assert _run("중단하세요", "오후 중후반 이후 카페인·에너지음료를 피하고, 음주는 중단하세요 [4].")


def test_drug_stop_directive_is_kept():
    """반대로 약을 끊으라는 지시는 반드시 보존돼야 한다."""
    assert not _run("중단하세요", "복용 중인 약을 중단하세요.")


def test_drug_take_directive_is_kept():
    assert not _run("복용하세요", "이 약을 아침마다 복용하세요.")


# ── 적대 검증: FP 필터가 실제 위험 지시를 놓치지 않는지 ──────
#
# analyzer 가 탐지한 위반은 FP 필터가 절대 지워선 안 된다. (탐지 자체를 못 하는
# 케이스는 공용 analyzer 의 별개 결함이라 여기서 다루지 않는다 — docs/plan/24 백로그.)

def test_permissive_directive_is_kept():
    """'…복용하시면 됩니다'도 지시다 — (h) 도입 때 놓쳤던 형태."""
    assert not _run("복용", "아스피린을 매일 복용하시면 됩니다.")


def test_dose_increase_directive_is_kept():
    assert not _run("올리세요", "메트포르민 용량을 올리세요.")


def test_non_hada_imperatives_are_kept():
    for verb, sent in [("늘리세요", "인슐린 약 용량을 2단위 늘리세요."),
                       ("줄이세요", "이 약을 반으로 줄이세요."),
                       ("바꾸세요", "기존 약을 끊고 이 약으로 바꾸세요."),
                       ("끊으세요", "복용 중인 약을 끊으세요.")]:
        assert not _run(verb, sent), sent
