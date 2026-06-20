"""
generate_response() 단위 테스트.

OpenAI API mock으로 실제 API 호출 없이 검증.
실제 통합 테스트는 @pytest.mark.integration 마커.

테스트 케이스:
  TC-1: 시스템 프롬프트에 4단 응답 구조 헤더 명시 확인
  TC-2: 가드레일 차단 — CRITICAL 위반 → 안전 메시지로 교체
  TC-3: 가드레일 재생성 — HIGH 위반 → fallback provider 1회 호출
  TC-4: 인용 검증 — 범위 벗어난 [N] 제거
  TC-5: 인용 검증 — 인용 0건 → fallback provider 재생성 시도
  TC-6: EMERGENCY 감지 → conversation state EMERGENCY_REDIRECTED 전환
  TC-7: EMERGENCY 상태에서 다음 호출 → 고정 응답 반환
  TC-8: 면책조항 자동 부착 — 면책조항 없는 응답에 bottom_disclaimer 추가
  TC-9: _extract_citations — [N] 마커 → chunk_id 매핑
  TC-10: _ensure_four_section_structure — 헤더 완전/누락 검증
  TC-11: _detect_emergency_signal — 응급 키워드 감지
  TC-12: generate_response STOP 이벤트에 필수 필드 포함

패치 전략:
  - get_llm_provider / get_fallback_provider는 rag_engine 내부에서
    'from llm_router import ...' 로컬 임포트로 사용된다.
  - 따라서 'llm_router.get_llm_provider' 를 패치한다.
  - ComplianceAnalyzer도 'rag_engine' 내부에서 from analyzer import 이므로
    'analyzer.ComplianceAnalyzer' 를 패치한다.
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, call

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════════════════════
#  Mock 헬퍼
# ════════════════════════════════════════════════════════════

def _make_chunk(chunk_id, content="의료 정보", score=0.5):
    return {
        "chunk_id": chunk_id,
        "document_id": f"doc_{chunk_id}",
        "content": content,
        "section_path": [],
        "source_id": "test_src",
        "evidence_level": "B",
        "evidence_topic": "fever",
        "severity": None,
        "score": score,
        "boost_reasons": [],
    }


def _make_provider_mock(response_text="테스트 응답입니다. [1]"):
    """stream_chat 이벤트를 생성하는 mock provider."""
    mock = MagicMock()
    mock.provider_id = "openai_gpt5"
    mock.model_id = "gpt-5"

    def stream_side_effect(system, user, **kwargs):
        yield {"type": "GENERATION", "text": response_text}
        yield {
            "type": "STOP",
            "text": response_text,
            "tokens": {"input": 100, "output": 50},
        }

    mock.stream_chat.side_effect = stream_side_effect
    return mock


def _make_fallback_mock(response_text="재생성된 안전 응답입니다. [1]"):
    """fallback provider mock."""
    mock = MagicMock()
    mock.provider_id = "openai_gpt5_mini"
    mock.model_id = "gpt-5-mini"

    def stream_side_effect(system, user, **kwargs):
        yield {"type": "GENERATION", "text": response_text}
        yield {
            "type": "STOP",
            "text": response_text,
            "tokens": {"input": 50, "output": 30},
        }

    mock.stream_chat.side_effect = stream_side_effect
    return mock


def _run_generate_response(
    query="두통이 있어요",
    conversation_id="conv-test-001",
    provider_id=None,
    mock_chunks=None,
    mock_provider=None,
    mock_analysis=None,
    mock_conv_state=None,
    enable_guardrails=True,
):
    """
    generate_response를 실행하는 공통 헬퍼.
    모든 외부 의존성을 mock으로 대체.

    rag_engine 내부 로컬 임포트:
      from llm_router import get_llm_provider  → llm_router.get_llm_provider 패치
      from analyzer import ComplianceAnalyzer  → analyzer.ComplianceAnalyzer 패치
    """
    if mock_chunks is None:
        mock_chunks = [_make_chunk("C1"), _make_chunk("C2")]
    if mock_provider is None:
        mock_provider = _make_provider_mock()
    if mock_analysis is None:
        # 기본: 위반 없음
        mock_analysis = MagicMock()
        mock_analysis.violations = []
    if mock_conv_state is None:
        mock_conv_state = {"emergency_state": "NORMAL"}

    with patch("rag_engine.hybrid_search", return_value=mock_chunks), \
         patch("llm_router.get_llm_provider", return_value=mock_provider), \
         patch("rag_engine._get_conversation_state", return_value=mock_conv_state), \
         patch("rag_engine._set_conversation_state"), \
         patch("rag_engine._insert_rag_query", return_value="rq-001"), \
         patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:

        MockAnalyzer.return_value.analyze.return_value = mock_analysis

        from rag_engine import generate_response
        events = list(generate_response(
            query=query,
            conversation_id=conversation_id,
            provider_id=provider_id,
            enable_guardrails=enable_guardrails,
        ))
    return events


# ════════════════════════════════════════════════════════════
#  TC-1: 시스템 프롬프트에 4단 구조 헤더 명시
# ════════════════════════════════════════════════════════════

class TestSystemPromptFourSections:
    def test_dynamic_emoji_header_guidance_in_system_prompt(self):
        """프롬프트가 고정 4단 대신 상황별 동적 헤더 + 이모지를 지시한다."""
        from rag_engine import _build_rag_system_prompt
        prompt = _build_rag_system_prompt("두통", [_make_chunk("C1")])
        # 고정 4단 강제 문구는 더 이상 없어야 함
        assert "반드시 4단 헤더" not in prompt
        # 동적 헤더 + 이모지 지시 존재
        assert "고정된 4단 구조를 쓰지 말고" in prompt
        assert "이모지" in prompt
        # 상황별 헤더 예시 이모지 일부 포함
        assert ("🩺" in prompt) or ("🚑" in prompt) or ("💊" in prompt)

    def test_system_prompt_contains_citation_instruction(self):
        """시스템 프롬프트에 인용 규칙 지침이 포함된다."""
        from rag_engine import _build_rag_system_prompt
        prompt = _build_rag_system_prompt("두통", [_make_chunk("C1")])
        assert "[번호]" in prompt or "인용" in prompt

    def test_system_prompt_contains_emergency_instruction(self):
        """시스템 프롬프트에 응급 안내 지침이 포함된다."""
        from rag_engine import _build_rag_system_prompt
        prompt = _build_rag_system_prompt("두통", [_make_chunk("C1")])
        assert "119" in prompt or "응급" in prompt


# ════════════════════════════════════════════════════════════
#  TC-2: 가드레일 차단 — CRITICAL 위반
# ════════════════════════════════════════════════════════════

class TestGuardrailCriticalBlock:
    def _critical_analysis(self):
        critical_v = MagicMock()
        critical_v.rule_id = "harmful_assumption"
        critical_v.severity = "CRITICAL"
        critical_v.matched_text = "자해"
        # context는 실제 analyzer가 문자열로 채운다. RAG 오탐필터가
        # context를 정규식 검사하므로 mock도 문자열이어야 한다(MagicMock이면
        # 필터가 TypeError→가드레일 우회). 부정/면책/용량 없는 문맥 → 보존됨.
        critical_v.context = "사용자가 자해 충동을 호소함"
        analysis = MagicMock()
        analysis.violations = [critical_v]
        return analysis

    def test_critical_violation_replaced_with_safe_message(self):
        """CRITICAL 위반 → 안전 메시지로 응답이 교체된다."""
        events = _run_generate_response(mock_analysis=self._critical_analysis())
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert "안전 기준" in stop_event["text"] or "의료진" in stop_event["text"]

    def test_critical_block_action_in_stop(self):
        """CRITICAL 차단 시 guardrail_action이 'blocked'다."""
        events = _run_generate_response(mock_analysis=self._critical_analysis())
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["guardrail_action"] == "blocked"

    def test_original_harmful_text_not_in_blocked_response(self):
        """차단된 경우 원본 유해 텍스트가 STOP 응답에 남지 않는다."""
        mock_provider = _make_provider_mock(
            response_text="자해 충동이 있으신가요? 자살 생각이 드시나요?"
        )
        events = _run_generate_response(
            mock_analysis=self._critical_analysis(),
            mock_provider=mock_provider,
        )
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert "자해 충동" not in stop_event["text"]


# ════════════════════════════════════════════════════════════
#  TC-3: 가드레일 재생성 — HIGH 위반
# ════════════════════════════════════════════════════════════

class TestGuardrailHighRegeneration:
    def _high_analysis(self, rule_id="emergency_guidance"):
        high_v = MagicMock()
        high_v.rule_id = rule_id
        high_v.severity = "HIGH"
        high_v.matched_text = "응급"
        # context는 문자열이어야 RAG 오탐필터가 정상 동작(MagicMock이면 우회).
        high_v.context = "응급 증상 가능성 언급"
        analysis = MagicMock()
        analysis.violations = [high_v]
        return analysis

    def test_high_violation_calls_fallback(self):
        """HIGH 위반 시 fallback provider가 호출된다."""
        fallback_mock = _make_fallback_mock("재생성된 응답입니다. [1]")

        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=_make_provider_mock()), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state"), \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("llm_router.get_fallback_provider", return_value=fallback_mock), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:

            MockAnalyzer.return_value.analyze.return_value = self._high_analysis()

            from rag_engine import generate_response
            events = list(generate_response("두통", "conv-001", enable_guardrails=True))

        # fallback stream_chat이 호출됐는지 확인
        assert fallback_mock.stream_chat.called

    def test_high_violation_action_is_regenerated(self):
        """HIGH 위반 시 guardrail_action에 'regenerated'가 포함된다."""
        fallback_mock = _make_fallback_mock("안전한 재생성 응답. [1] 의료진 상담 권고.")

        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=_make_provider_mock()), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state"), \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("llm_router.get_fallback_provider", return_value=fallback_mock), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:

            MockAnalyzer.return_value.analyze.return_value = self._high_analysis("diagnosis_direct")

            from rag_engine import generate_response
            events = list(generate_response("두통", "conv-001", enable_guardrails=True))

        stop_event = next(e for e in events if e["type"] == "STOP")
        assert "regenerated" in stop_event["guardrail_action"]


# ════════════════════════════════════════════════════════════
#  TC-4: 인용 검증 — 범위 벗어난 [N] 제거
# ════════════════════════════════════════════════════════════

class TestCitationValidation:
    def test_out_of_range_citation_removed(self):
        """chunks가 2개일 때 [3]은 제거된다."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2")]
        text = "관련 정보 [1][3] 참조."
        fixed, action = _validate_and_fix_citations(text, chunks)
        assert "[3]" not in fixed
        assert "[1]" in fixed

    def test_valid_citation_preserved(self):
        """유효한 [N] 인용은 제거되지 않는다."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2")]
        text = "정보 [1] 및 [2] 참조."
        fixed, action = _validate_and_fix_citations(text, chunks)
        assert "[1]" in fixed
        assert "[2]" in fixed

    def test_action_fixed_when_citation_removed(self):
        """인용 제거 시 action이 'fixed'다."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1")]
        text = "내용 [1][5] 참조."
        _, action = _validate_and_fix_citations(text, chunks)
        assert action == "fixed"

    def test_action_pass_when_all_valid(self):
        """모든 인용이 유효하면 action이 'pass'다."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2")]
        text = "내용 [1] [2] 참조."
        _, action = _validate_and_fix_citations(text, chunks)
        assert action == "pass"

    def test_zero_chunks_skips_validation(self):
        """chunks가 없으면 검증 스킵 — 원본 텍스트 반환."""
        from rag_engine import _validate_and_fix_citations
        text = "인용 [1] 테스트."
        fixed, action = _validate_and_fix_citations(text, [])
        assert fixed == text
        assert action == "pass"


# ════════════════════════════════════════════════════════════
#  TC-5: 인용 0건 → fallback 재생성
# ════════════════════════════════════════════════════════════

class TestCitationZeroRegeneration:
    def test_zero_citations_triggers_fallback(self):
        """인용이 0건이면 fallback provider가 호출된다."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2")]
        text_no_citation = "두통은 여러 원인이 있습니다. 충분한 휴식이 필요합니다."

        fallback_mock = MagicMock()
        fallback_mock.stream_chat.return_value = iter([
            {"type": "STOP", "text": "개선된 응답 [1] 참조.", "tokens": {}}
        ])

        with patch("llm_router.get_fallback_provider", return_value=fallback_mock):
            fixed, action = _validate_and_fix_citations(
                text_no_citation, chunks,
                system_prompt="테스트 시스템",
                user_prompt="테스트 사용자"
            )

        assert fallback_mock.stream_chat.called
        assert action == "regenerated"

    def test_zero_citations_no_system_prompt_no_regen(self):
        """system_prompt가 없으면 재생성 시도 안 함."""
        from rag_engine import _validate_and_fix_citations
        chunks = [_make_chunk("C1")]
        text = "인용 없는 응답입니다."
        # system_prompt 미전달
        fixed, action = _validate_and_fix_citations(text, chunks)
        # 재생성 없이 pass 유지
        assert action in ("pass", "fixed")


# ════════════════════════════════════════════════════════════
#  TC-6: EMERGENCY 감지 → 상태 전환
# ════════════════════════════════════════════════════════════

class TestMultiturnWiring:
    """멀티턴 배선 end-to-end: 후속질의가 검색 단계에서 재작성되는지 검증."""

    def test_followup_rewrites_hybrid_search_query(self):
        from unittest.mock import MagicMock
        spy = MagicMock(return_value=[_make_chunk("C1")])
        analysis = MagicMock()
        analysis.violations = []
        with patch("rag_engine.hybrid_search", spy), \
             patch("conversation_context.load_context", return_value={
                 "last_symptom_keys": ["headache"], "last_intent": "symptom_info",
                 "last_departments": ["신경과"], "turn_count": 1}), \
             patch("conversation_context.update_context"), \
             patch("llm_router.get_llm_provider", return_value=_make_provider_mock()), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:
            MockAnalyzer.return_value.analyze.return_value = analysis
            from rag_engine import generate_response
            list(generate_response("언제 병원 가야 해요?", "conv-mt-1", enable_guardrails=True))

        # hybrid_search가 *재작성된* 질의로 호출되어야 함(원본과 다름)
        called_query = spy.call_args[0][0]
        assert called_query != "언제 병원 가야 해요?", "검색 질의가 재작성되지 않음"
        assert "진료" in called_query, f"재작성 템플릿 누락: {called_query}"

    def test_emergency_followup_not_rewritten(self):
        """후속 신호가 있어도 이번 턴이 응급이면 재작성하지 않는다(안전)."""
        from unittest.mock import MagicMock
        spy = MagicMock(return_value=[_make_chunk("C1")])
        analysis = MagicMock()
        analysis.violations = []
        with patch("rag_engine.hybrid_search", spy), \
             patch("conversation_context.load_context", return_value={
                 "last_symptom_keys": ["headache"], "last_intent": "symptom_info",
                 "last_departments": ["신경과"], "turn_count": 1}), \
             patch("conversation_context.update_context"), \
             patch("llm_router.get_llm_provider", return_value=_make_provider_mock()), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:
            MockAnalyzer.return_value.analyze.return_value = analysis
            from rag_engine import generate_response
            # 응급 신호 + 후속처럼 짧은 질의
            list(generate_response("숨을 못 쉬겠어요", "conv-mt-2", enable_guardrails=True))

        called_query = spy.call_args[0][0]
        assert called_query == "숨을 못 쉬겠어요", "응급 질의가 재작성됨(안전 위반)"


class TestGuardrailFailSafe:
    """가드레일 예외 시 fail-open이 아니라 감사가능·면책보장으로 처리."""

    def test_guardrail_exception_marks_error_and_keeps_disclaimer(self):
        """analyzer가 예외를 던지면 guardrail_action='error'로 표시되고
        면책문구가 부착된다(예외를 'pass'로 오라벨하지 않음)."""
        mock_provider = _make_provider_mock(response_text="두통 정보입니다. [1]")
        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=mock_provider), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state"), \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:
            MockAnalyzer.return_value.analyze.side_effect = RuntimeError("analyzer boom")

            from rag_engine import generate_response
            events = list(generate_response(
                "두통이 있어요", "conv-err-001", enable_guardrails=True
            ))

        stop = next(e for e in events if e["type"] == "STOP")
        assert stop["guardrail_action"] == "error", \
            f"가드레일 예외가 'error'로 표시되지 않음: {stop['guardrail_action']}"
        # 예외 시에도 면책문구가 부착되어야 함
        assert ("건강정보" in stop["text"]) or ("의료진" in stop["text"]), \
            "가드레일 예외 시 면책문구 누락"


class TestEmergencyDetection:
    def test_emergency_keyword_triggers_state_change(self):
        """응답에 '119'가 포함되면 _set_conversation_state가 EMERGENCY_REDIRECTED로 호출된다."""
        mock_provider = _make_provider_mock(
            response_text=(
                "【① 즉시 행동】 119에 즉시 연락하거나 응급실로 이동하세요.\n"
                "【② 의심 원인 요약】 심장 관련 가능성\n"
                "【③ 상세 설명】 흉통은 심각한 원인이 있을 수 있습니다. [1]\n"
                "【④ 추가 확인 사항】 응급 처치 후 추가 확인 필요\n"
                "※ 의료진과 상담하시기 바랍니다."
            )
        )
        analysis = MagicMock()
        analysis.violations = []

        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=mock_provider), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state") as mock_set_state, \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:

            MockAnalyzer.return_value.analyze.return_value = analysis

            from rag_engine import generate_response
            list(generate_response("흉통이 심해요", "conv-emrg-001", enable_guardrails=True))

        # EMERGENCY_REDIRECTED로 상태 전환 호출 확인
        mock_set_state.assert_called_once_with("conv-emrg-001", "EMERGENCY_REDIRECTED")

    def test_non_emergency_response_no_state_change(self):
        """응급 키워드가 없으면 _set_conversation_state가 호출되지 않는다."""
        mock_provider = _make_provider_mock(
            response_text=(
                "【① 즉시 행동】 충분한 수분을 섭취하세요.\n"
                "【② 의심 원인 요약】 일반적인 두통\n"
                "【③ 상세 설명】 [1] 두통은 다양한 원인이 있습니다.\n"
                "【④ 추가 확인 사항】 3일 이상 지속시 병원 방문 권고\n"
                "※ 의료진과 상담하시기 바랍니다."
            )
        )
        analysis = MagicMock()
        analysis.violations = []

        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=mock_provider), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state") as mock_set_state, \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:

            MockAnalyzer.return_value.analyze.return_value = analysis

            from rag_engine import generate_response
            list(generate_response("두통이 가끔 있어요", "conv-normal-001", enable_guardrails=True))

        mock_set_state.assert_not_called()

    def test_cautionary_119_in_answer_does_not_latch_emergency(self):
        """비응급 질의의 답변이 조건부 '119/응급실' 안내를 포함해도 EMERGENCY로
        잠그지 않는다(과대 트리아지 고착 버그 회귀 — 질의 분류 기준 판정)."""
        mock_provider = _make_provider_mock(
            response_text=(
                "【① 즉시 행동】 머리 외상이 있으면 즉시 119 또는 응급실을 이용하세요.\n"
                "【② 의심 원인 요약】 일반적인 두통\n"
                "【③ 상세 설명】 [1] 휴식이 도움이 됩니다.\n"
                "【④ 추가 확인 사항】 지속되면 신경과 상담을 고려하세요.\n"
            )
        )
        analysis = MagicMock()
        analysis.violations = []
        with patch("rag_engine.hybrid_search", return_value=[_make_chunk("C1")]), \
             patch("llm_router.get_llm_provider", return_value=mock_provider), \
             patch("rag_engine._get_conversation_state", return_value={"emergency_state": "NORMAL"}), \
             patch("rag_engine._set_conversation_state") as mock_set, \
             patch("rag_engine._insert_rag_query", return_value="rq-001"), \
             patch("analyzer.ComplianceAnalyzer") as MockAnalyzer:
            MockAnalyzer.return_value.analyze.return_value = analysis
            from rag_engine import generate_response
            # 질의는 비응급(두통/symptom_info) — 답변에 119가 있어도 잠그면 안 됨
            list(generate_response("3일째 머리가 아파", "conv-headache", enable_guardrails=True))
        mock_set.assert_not_called()


# ════════════════════════════════════════════════════════════
#  TC-7: EMERGENCY 상태에서 고정 응답
# ════════════════════════════════════════════════════════════

class TestEmergencyRedirectedState:
    def test_emergency_redirected_returns_fixed_message(self):
        """EMERGENCY_REDIRECTED 상태면 고정 응답을 반환한다."""
        with patch("rag_engine.hybrid_search") as mock_search, \
             patch("rag_engine._get_conversation_state",
                   return_value={"emergency_state": "EMERGENCY_REDIRECTED"}):

            from rag_engine import generate_response
            events = list(generate_response("새 증상이 있어요", "conv-emrg-redirected"))

        # hybrid_search는 호출되지 않아야 함
        mock_search.assert_not_called()

        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        stop_event = stop_events[0]
        # 고정 응답 키워드 확인
        assert "응급" in stop_event["text"] or "119" in stop_event["text"]

    def test_emergency_redirected_guardrail_action(self):
        """EMERGENCY_REDIRECTED 상태 응답의 guardrail_action은 'emergency_redirect'다."""
        with patch("rag_engine._get_conversation_state",
                   return_value={"emergency_state": "EMERGENCY_REDIRECTED"}):
            from rag_engine import generate_response
            events = list(generate_response("다른 질문", "conv-emrg"))

        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["guardrail_action"] == "emergency_redirect"

    def test_emergency_redirected_no_rag_query_id(self):
        """EMERGENCY_REDIRECTED 상태 응답에는 rag_query_id가 None이다."""
        with patch("rag_engine._get_conversation_state",
                   return_value={"emergency_state": "EMERGENCY_REDIRECTED"}):
            from rag_engine import generate_response
            events = list(generate_response("질문", "conv-emrg"))

        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["rag_query_id"] is None


# ════════════════════════════════════════════════════════════
#  TC-8: 면책조항 자동 부착
# ════════════════════════════════════════════════════════════

class TestDisclaimerEnsure:
    def test_disclaimer_appended_when_missing(self):
        """면책조항 키워드가 없는 텍스트에 면책조항이 부착된다."""
        from rag_engine import _ensure_disclaimer
        text = "두통에는 충분한 수분을 섭취하는 것이 도움이 됩니다."
        result = _ensure_disclaimer(text)
        # 면책조항 관련 키워드 포함 확인
        disclaimer_keywords = ["의료진", "상담", "전문의", "병원 방문", "진료"]
        assert any(kw in result for kw in disclaimer_keywords)

    def test_disclaimer_not_duplicated_when_present(self):
        """이미 면책조항이 있으면 중복 부착하지 않는다."""
        from rag_engine import _ensure_disclaimer
        text = "두통 정보입니다. 반드시 의료진과 상담하세요."
        result = _ensure_disclaimer(text)
        # 원본 텍스트 포함 확인
        assert "의료진과 상담" in result

    def test_disclaimer_text_appended_to_end(self):
        """면책조항은 원본 텍스트 끝에 부착된다."""
        from rag_engine import _ensure_disclaimer
        text = "짧은 응답입니다."
        result = _ensure_disclaimer(text)
        assert result.startswith("짧은 응답입니다.")
        assert len(result) > len(text)


# ════════════════════════════════════════════════════════════
#  TC-9: _extract_citations
# ════════════════════════════════════════════════════════════

class TestExtractCitations:
    def test_citation_mapped_to_chunk_id(self):
        """[1] → 첫 번째 청크 ID로 매핑된다."""
        from rag_engine import _extract_citations
        chunks = [_make_chunk("CHUNK-A"), _make_chunk("CHUNK-B")]
        text = "정보 [1] 참조."
        citations = _extract_citations(text, chunks)
        assert len(citations) == 1
        assert citations[0]["marker"] == "[1]"
        assert citations[0]["chunk_id"] == "CHUNK-A"

    def test_multiple_citations_mapped(self):
        """[1], [2] → 각각 매핑."""
        from rag_engine import _extract_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2"), _make_chunk("C3")]
        text = "정보 [2] 및 [1] 참조."
        citations = _extract_citations(text, chunks)
        cids = {c["chunk_id"] for c in citations}
        assert "C1" in cids
        assert "C2" in cids

    def test_out_of_range_citation_excluded(self):
        """범위 벗어난 [N]은 citations에 포함되지 않는다."""
        from rag_engine import _extract_citations
        chunks = [_make_chunk("C1")]
        text = "[1] [5] 참조."
        citations = _extract_citations(text, chunks)
        markers = [c["marker"] for c in citations]
        assert "[1]" in markers
        assert "[5]" not in markers

    def test_duplicate_citation_deduplicated(self):
        """같은 [N]이 여러 번 등장해도 중복 없이 한 번만 포함."""
        from rag_engine import _extract_citations
        chunks = [_make_chunk("C1"), _make_chunk("C2")]
        text = "[1] 내용 [1] 더 내용."
        citations = _extract_citations(text, chunks)
        markers = [c["marker"] for c in citations]
        assert markers.count("[1]") == 1

    def test_no_citations_returns_empty(self):
        """인용 없는 텍스트 → 빈 리스트."""
        from rag_engine import _extract_citations
        chunks = [_make_chunk("C1")]
        text = "인용 없는 응답입니다."
        citations = _extract_citations(text, chunks)
        assert citations == []


# ════════════════════════════════════════════════════════════
#  TC-10: _has_section_structure (동적 헤더 — 2개 이상이면 통과)
# ════════════════════════════════════════════════════════════

class TestSectionStructure:
    def test_emoji_headers_pass(self):
        """이모지 마크다운 헤더 2개 이상이면 True."""
        from rag_engine import _has_section_structure
        text = (
            "## 🩺 지금 상황\n- 내용 [1]\n"
            "## 💡 가능한 원인\n- 내용 [2]\n"
            "## ❓ 더 정확히 알려면\n- 질문"
        )
        assert _has_section_structure(text) is True

    def test_legacy_bracket_headers_pass(self):
        """구형 【…】 헤더도 헤더로 인식(하위호환)."""
        from rag_engine import _has_section_structure
        text = "【① 즉시 행동】 조치\n【② 의심 원인 요약】 원인"
        assert _has_section_structure(text) is True

    def test_single_header_returns_false(self):
        """헤더 1개뿐이면 구조 부족 → False."""
        from rag_engine import _has_section_structure
        assert _has_section_structure("## 🩺 지금 상황\n내용만 길게...") is False

    def test_no_header_returns_false(self):
        """헤더 없는 평문 → False."""
        from rag_engine import _has_section_structure
        assert _has_section_structure("그냥 줄글 답변입니다. 헤더가 없습니다.") is False

    def test_empty_text_returns_false(self):
        from rag_engine import _has_section_structure
        assert _has_section_structure("") is False

    def test_legacy_alias_exists(self):
        """기존 호출부 호환 별칭 유지."""
        from rag_engine import _ensure_four_section_structure, _has_section_structure
        assert _ensure_four_section_structure is _has_section_structure


# ════════════════════════════════════════════════════════════
#  TC-11: _detect_emergency_signal
# ════════════════════════════════════════════════════════════

class TestDetectEmergencySignal:
    def test_119_detected(self):
        """'119' 포함 → True."""
        from rag_engine import _detect_emergency_signal
        assert _detect_emergency_signal("즉시 119에 신고하세요.") is True

    def test_emergency_room_detected(self):
        """'응급실' 포함 → True."""
        from rag_engine import _detect_emergency_signal
        assert _detect_emergency_signal("응급실로 이동하세요.") is True

    def test_no_emergency_keyword(self):
        """응급 키워드 없음 → False."""
        from rag_engine import _detect_emergency_signal
        assert _detect_emergency_signal("두통에는 휴식이 필요합니다.") is False

    def test_urgent_keyword_detected(self):
        """'긴급' 포함 → True."""
        from rag_engine import _detect_emergency_signal
        assert _detect_emergency_signal("긴급 상황입니다.") is True


# ════════════════════════════════════════════════════════════
#  TC-12: generate_response STOP 이벤트 필수 필드
# ════════════════════════════════════════════════════════════

class TestGenerateResponseStopEvent:
    def test_stop_event_required_fields(self):
        """STOP 이벤트에 필수 필드가 모두 있다."""
        events = _run_generate_response(enable_guardrails=False)
        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        stop = stop_events[0]

        required_fields = ["text", "rag_query_id", "citations", "latency_ms", "tokens", "guardrail_action"]
        for f in required_fields:
            assert f in stop, f"STOP 이벤트에 필드 누락: {f}"

    def test_info_event_has_search_results(self):
        """INFO 이벤트 중 정확히 하나가 search_results를 포함한다.

        generate_response는 'started' 상태 INFO와 search_results INFO를
        각각 1회 emit한다(총 INFO 2개). 여기서는 후자의 존재를 검증한다.
        """
        events = _run_generate_response(enable_guardrails=False)
        sr_events = [
            e for e in events
            if e["type"] == "INFO" and "search_results" in e.get("data", {})
        ]
        assert len(sr_events) == 1

    def test_generation_events_present(self):
        """GENERATION 이벤트가 최소 1개 있다."""
        events = _run_generate_response(enable_guardrails=False)
        gen_events = [e for e in events if e["type"] == "GENERATION"]
        assert len(gen_events) >= 1

    def test_guardrails_disabled_action_pass(self):
        """가드레일 비활성화 시 guardrail_action이 'pass'다."""
        events = _run_generate_response(enable_guardrails=False)
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["guardrail_action"] == "pass"

    def test_rag_query_id_in_stop_event(self):
        """STOP 이벤트의 rag_query_id가 None이 아니다 (정상 흐름)."""
        events = _run_generate_response(enable_guardrails=False)
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["rag_query_id"] == "rq-001"

    def test_tokens_dict_structure(self):
        """tokens 딕셔너리에 input, output 키가 있다."""
        events = _run_generate_response(enable_guardrails=False)
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert "input" in stop_event["tokens"]
        assert "output" in stop_event["tokens"]


# ════════════════════════════════════════════════════════════
#  _build_rag_user_prompt 단위 테스트
# ════════════════════════════════════════════════════════════

class TestBuildRagUserPrompt:
    def test_citation_numbers_in_prompt(self):
        """청크가 N개면 [1]~[N] 번호가 프롬프트에 있다."""
        from rag_engine import _build_rag_user_prompt
        chunks = [_make_chunk("C1"), _make_chunk("C2"), _make_chunk("C3")]
        prompt = _build_rag_user_prompt("두통", chunks)
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "[3]" in prompt

    def test_query_in_prompt(self):
        """사용자 질의가 프롬프트에 포함된다."""
        from rag_engine import _build_rag_user_prompt
        chunks = [_make_chunk("C1")]
        query = "흉통이 심합니다"
        prompt = _build_rag_user_prompt(query, chunks)
        assert query in prompt

    def test_source_id_in_prompt(self):
        """source_id가 출처 정보로 프롬프트에 포함된다."""
        from rag_engine import _build_rag_user_prompt
        c = _make_chunk("C1", content="테스트 내용")
        c["source_id"] = "kdca_guideline"
        prompt = _build_rag_user_prompt("질문", [c])
        assert "kdca_guideline" in prompt

    def test_empty_chunks_no_citation(self):
        """청크가 없으면 [N] 번호 없이 질의만 포함된다."""
        from rag_engine import _build_rag_user_prompt
        prompt = _build_rag_user_prompt("질문", [])
        assert "[1]" not in prompt
        assert "질문" in prompt


# ════════════════════════════════════════════════════════════
#  _build_emergency_response 단위 테스트
# ════════════════════════════════════════════════════════════

class TestBuildEmergencyResponse:
    def test_contains_119(self):
        """고정 응답에 119가 포함된다."""
        from rag_engine import _build_emergency_response
        assert "119" in _build_emergency_response()

    def test_contains_new_conversation_hint(self):
        """새 대화 시작 안내가 포함된다."""
        from rag_engine import _build_emergency_response
        msg = _build_emergency_response()
        assert "새 대화" in msg or "새로운" in msg


# ════════════════════════════════════════════════════════════
#  TC-통합: @pytest.mark.integration
# ════════════════════════════════════════════════════════════

_needs_postgres = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — PostgreSQL integration tests skipped",
)
_needs_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — integration tests skipped",
)


@pytest.mark.integration
@_needs_postgres
@_needs_openai
class TestIntegration:
    def test_generate_response_full_flow(self):
        """실제 PostgreSQL + OpenAI로 전체 흐름 검증."""
        from rag_engine import generate_response
        events = list(generate_response(
            query="두통의 일반적인 원인은 무엇인가요?",
            conversation_id="test-conv-integration",
            enable_guardrails=True,
        ))
        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        assert len(stop_events[0]["text"]) > 0
        assert stop_events[0]["rag_query_id"] is not None
