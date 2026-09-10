# -*- coding: utf-8 -*-
"""답변 스타일 프로필 — persly-safe 형식 층은 켜되 답변 범위(L0~L3)는 그대로.

정본: docs/persly_style_260910/README.md
persly-full(L5·L6 + 가드레일 우회)은 의도적 미구현 — 알 수 없는 값은 default 폴백.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import answer_style as A  # noqa: E402
from rag_engine import _build_rag_system_prompt as B  # noqa: E402


# ── 프로필 해석 ──────────────────────────────────────────────

def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("ANSWER_STYLE", raising=False)
    assert A.resolve(None) == "default"
    assert A.resolve("") == "default"


def test_persly_safe_resolves():
    assert A.resolve("persly-safe") == "persly-safe"
    assert A.resolve("  PERSLY-SAFE ") == "persly-safe"


def test_persly_full_falls_back_to_default():
    # 안전 완화 프로필은 미구현 — 알 수 없는 값이 완화로 이어지면 안 된다
    assert A.resolve("persly-full") == "default"
    assert A.resolve("아무거나") == "default"


def test_env_used_when_no_request(monkeypatch):
    monkeypatch.setenv("ANSWER_STYLE", "persly-safe")
    assert A.resolve(None) == "persly-safe"
    # 요청값이 지원되면 요청이 이긴다
    assert A.resolve("default") == "default"


# ── 프롬프트 본문 ────────────────────────────────────────────

def test_default_prompt_unchanged_by_style_param():
    assert B("q", [], personal_kind="raw") == B("q", [], personal_kind="raw", style="default")


def test_persly_safe_has_four_slots_and_no_reask():
    p = B("q", [], personal_kind="raw", style="persly-safe")
    for slot in ("가능한 원인", "지금 당장의 안전 체크",
                 "집에서 해볼 수 있는 관리", "사용자 기록과 연결해 보면"):
        assert slot in p
    assert "되묻지 않습니다" in p
    assert "[제안 질문]" in p


def test_persly_safe_keeps_answer_scope_bans():
    """형식만 바뀌고 L4~L6 금지는 유지돼야 한다."""
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "질환명을 사람에게 붙이지 않습니다" in p
    assert "검사명 나열 금지" in p
    assert "진료과·의료기관 지정" in p          # 금지 목록에 있음
    assert "확정 진단" in p and "원인 단정" in p


def test_persly_safe_bans_drug_recommendation():
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "일반의약품 계열도 권하지 않습니다" in p
    assert "용량·복용법·특정 제품 지시" in p


def test_version_per_profile():
    assert A.version_of("default") == "answer-scope-260910"
    assert A.version_of("persly-safe") == "persly-safe-260910"
    assert A.version_of("persly-full") == "answer-scope-260910"   # 폴백


# ── [제안 질문] 꼬리 분리 ────────────────────────────────────

def test_split_suggested_extracts_two():
    t = "본문입니다.\n\n[제안 질문]\n- A와 B 중 무엇이 먼저인가요?\n- C는 언제 하나요?\n"
    body, qs = A.split_suggested(t)
    assert "[제안 질문]" not in body
    assert body.endswith("본문입니다.")
    assert qs == ["A와 B 중 무엇이 먼저인가요?", "C는 언제 하나요?"]


def test_split_suggested_noop_without_marker():
    body, qs = A.split_suggested("그냥 본문")
    assert body == "그냥 본문" and qs == []


def test_split_suggested_caps_at_two():
    t = "본문\n[제안 질문]\n- 1\n- 2\n- 3\n"
    _, qs = A.split_suggested(t)
    assert len(qs) == 2


def test_split_suggested_keeps_leading_number():
    """불릿만 떼고 질문 앞 숫자는 남긴다 ("2주 뒤에…"가 "주 뒤에…"가 되면 안 됨)."""
    t = "본문\n[제안 질문]\n- 2주 뒤에 다시 재보는 게 좋을까요?\n"
    _, qs = A.split_suggested(t)
    assert qs == ["2주 뒤에 다시 재보는 게 좋을까요?"]


def test_split_suggested_numeric_bullet():
    t = "본문\n[제안 질문]\n1. 첫째인가요?\n2) 둘째인가요?\n"
    _, qs = A.split_suggested(t)
    assert qs == ["첫째인가요?", "둘째인가요?"]


def test_persly_safe_has_no_literal_placeholder():
    """[N]을 그대로 두면 모델이 문자 N을 출력해 인용이 0건이 된다(실측)."""
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "[N]" not in p
    assert "실제\n   자료 번호" in p or "실제 자료 번호" in p.replace("\n   ", " ")
