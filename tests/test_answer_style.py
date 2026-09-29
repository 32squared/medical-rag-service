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


def test_persly_safe_bans_record_based_inference():
    """실측: 처방 기록에서 "혈당 관리 중인 것으로 보입니다"를 만들어냈다(L4)."""
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "인 것으로 보입니다" in p and "금지" in p
    assert "조제 사실까지만" in p


# ── 소제목 굵게 보정 (모델이 평문 한 줄로 쓴 네 소제목) ─────────────
# dev persly-safe PHR 답(rev 00064)에서 소제목이 평문으로 온 모양 그대로.

_PLAIN = ("'공복혈당'은 일반 참고범위(100 미만)와 비교하면 118은 범위 밖(높음)입니다 [1].\n\n"
          "가능한 원인 2가지\n- 식사·운동 패턴의 영향: 활동량이 줄면 공복 혈당이 오를 수 있습니다 [1].\n\n"
          "지금 당장의 안전 체크\n- 심한 떨림, 식은땀이 반복될 때\n\n"
          "집에서 해볼 수 있는 관리\n- 식후 걷기: 식후 30분 이내에 20분 걷기를 4주 해 보세요 [1].\n\n"
          "사용자 기록과 연결해 보면\n- 공복혈당 118(2025-03)은 참고범위 밖입니다 [내 기록].")


def test_bold_slot_titles_fixes_plain_title_lines():
    from rag_engine import _has_section_structure
    out = A.bold_slot_titles(_PLAIN)
    for t in ("**가능한 원인 2가지**", "**지금 당장의 안전 체크**",
              "**집에서 해볼 수 있는 관리**", "**사용자 기록과 연결해 보면**"):
        assert t in out
    assert not _has_section_structure(_PLAIN)
    assert _has_section_structure(out)


def test_bold_slot_titles_leaves_body_bold_and_heading_lines():
    s = ("**가능한 원인 2가지**\n- 가능한 원인 중 하나는 수면 부족입니다.\n"
         "집에서 해볼 수 있는 관리를 2주 해 보세요.\n### 지금 당장의 안전 체크")
    assert A.bold_slot_titles(s) == s


def test_bold_slot_titles_accepts_colon_count_and_indent():
    assert A.bold_slot_titles("가능한 원인 3가지:") == "**가능한 원인 3가지**"
    assert A.bold_slot_titles("  지금 당장의 안전 체크 ") == "  **지금 당장의 안전 체크**"
    assert A.bold_slot_titles("") == ""


def _stop_event(style, text):
    from unittest.mock import MagicMock, patch
    prov = MagicMock()
    prov.provider_id, prov.model_id = "openai_gpt5", "gpt-5"

    def _stream(system, user, **kw):
        yield {"type": "GENERATION", "text": text}
        yield {"type": "STOP", "text": text, "tokens": {"input": 1, "output": 1}}

    prov.stream_chat.side_effect = _stream
    analysis = MagicMock()
    analysis.violations = []
    chunks = [{"chunk_id": c, "document_id": f"doc_{c}", "content": "공복혈당 참고 정보",
               "section_path": [], "source_id": "test_src", "evidence_level": "B",
               "evidence_topic": "공복혈당", "severity": None, "score": 0.6, "boost_reasons": []}
              for c in ("C1", "C2")]
    with patch("rag_engine.hybrid_search", return_value=chunks), \
         patch("llm_router.get_llm_provider", return_value=prov), \
         patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
         patch("rag_engine._set_conversation_state"), \
         patch("rag_engine._insert_rag_query", return_value="rq-bold"), \
         patch("analyzer.ComplianceAnalyzer") as MA:
        MA.return_value.analyze.return_value = analysis
        from rag_engine import generate_response
        events = list(generate_response(query="공복혈당은 어떤 편인가요?",
                                        conversation_id=f"conv-bold-{style}", answer_style=style))
    return [e for e in events if e["type"] == "STOP"][-1]


def test_generate_response_bolds_slot_titles_for_persly_safe_only():
    stop = _stop_event("persly-safe", _PLAIN)
    assert "**가능한 원인 2가지**" in stop["text"]
    assert stop["guardrail_action"] != "missing_structure"
    stop = _stop_event("default", _PLAIN)
    assert "**가능한 원인 2가지**" not in stop["text"]
