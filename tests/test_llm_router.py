"""
llm_router.py 단위 테스트.

OpenAI API mock으로 실제 API 호출 없이 검증.
실제 API 통합 테스트는 @pytest.mark.integration 마커.

테스트 케이스:
  TC-1: OpenAIProvider 초기화 — model_id, provider_id 검증
  TC-2: OpenAIProvider.stream_chat — GENERATION / STOP 청크 형식
  TC-3: OpenAIProvider.stream_chat — 오류 시 ERROR 청크 반환
  TC-4: OpenAIProvider.stream_chat — delta.content=None 방어 코드
  TC-5: OpenAIProvider.stream_chat — usage 토큰 파싱
  TC-6: get_llm_provider 팩토리 — 기본값 / 명시적 provider_id
  TC-7: get_llm_provider 팩토리 — 알 수 없는 provider_id → ValueError
  TC-8: get_fallback_provider — gpt-5.4-mini 반환
  TC-9: get_llm_provider — RAG_LLM_DEFAULT_PROVIDER 환경변수 우선
  TC-10: OpenAIProvider API 키 없으면 ValueError
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════════════════════
#  Mock 헬퍼
# ════════════════════════════════════════════════════════════

def _make_stream_chunk(content=None, prompt_tokens=None, completion_tokens=None):
    """OpenAI 스트리밍 청크 mock 생성."""
    chunk = MagicMock()
    choice = MagicMock()
    choice.delta = MagicMock()
    choice.delta.content = content
    chunk.choices = [choice]

    if prompt_tokens is not None or completion_tokens is not None:
        chunk.usage = MagicMock()
        chunk.usage.prompt_tokens = prompt_tokens
        chunk.usage.completion_tokens = completion_tokens
    else:
        chunk.usage = None

    return chunk


def _make_openai_provider(model_id="gpt-5", api_key="test-key"):
    """OpenAI SDK mock을 패치하여 OpenAIProvider 인스턴스 반환."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": api_key}):
        with patch("llm_router.OpenAIProvider.__init__", lambda self, model_id=model_id, api_key=api_key: None):
            from llm_router import OpenAIProvider
            provider = OpenAIProvider.__new__(OpenAIProvider)
            provider._model_id = model_id
            provider._api_key = api_key
            provider._provider_id = "openai_" + model_id.replace("-", "_")
            mock_client = MagicMock()
            provider._client = mock_client
            return provider, mock_client


# ════════════════════════════════════════════════════════════
#  TC-1: OpenAIProvider 초기화
# ════════════════════════════════════════════════════════════

def _make_openai_provider_direct(model_id="gpt-5"):
    """
    OpenAIProvider를 직접 생성 (openai.OpenAI 클라이언트 mock 주입).
    이미 임포트된 llm_router 모듈의 OpenAI 참조를 패치한다.
    """
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch("llm_router.OpenAIProvider._client", create=True):
            # OpenAI 클라이언트 생성을 우회하기 위해 llm_router 내 openai 모듈 패치
            import llm_router as _lr
            orig = getattr(_lr, "_openai_client_cls", None)
            # OpenAI import 패치
            import openai as _openai
            original_cls = _openai.OpenAI
            _openai.OpenAI = MagicMock(return_value=MagicMock())
            try:
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id=model_id)
            finally:
                _openai.OpenAI = original_cls
    return p


class TestOpenAIProviderInit:
    def test_model_id_and_provider_id(self):
        """model_id, provider_id가 올바르게 설정된다."""
        p = _make_openai_provider_direct("gpt-5")
        assert p.model_id == "gpt-5"
        assert p.provider_id == "openai_gpt5"

    def test_gpt5_mini_provider_id(self):
        """gpt-5-mini의 provider_id는 openai_gpt5_mini."""
        p = _make_openai_provider_direct("gpt-5-mini")
        assert p.model_id == "gpt-5-mini"
        assert p.provider_id == "openai_gpt5_mini"

    def test_model_id_from_env(self):
        """RAG_LLM_MODEL 환경변수가 없으면 gpt-5.4-mini 기본값 사용."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            os.environ.pop("RAG_LLM_MODEL", None)
            import openai as _openai
            original_cls = _openai.OpenAI
            _openai.OpenAI = MagicMock(return_value=MagicMock())
            try:
                from llm_router import OpenAIProvider
                p = OpenAIProvider()
            finally:
                _openai.OpenAI = original_cls
        assert p.model_id == "gpt-5.4-mini"

    def test_abstract_interface_properties(self):
        """provider_id, model_id 프로퍼티가 존재한다."""
        p = _make_openai_provider_direct("gpt-5")
        assert hasattr(p, "provider_id")
        assert hasattr(p, "model_id")
        assert hasattr(p, "stream_chat")


# ════════════════════════════════════════════════════════════
#  TC-10: API 키 미설정 → ValueError
# ════════════════════════════════════════════════════════════

class TestOpenAIProviderAPIKey:
    def test_missing_api_key_raises(self):
        """OPENAI_API_KEY 없으면 ValueError 발생."""
        env_backup = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                with patch("openai.OpenAI"):
                    from llm_router import OpenAIProvider
                    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                        OpenAIProvider(model_id="gpt-5", api_key=None)
        finally:
            if env_backup is not None:
                os.environ["OPENAI_API_KEY"] = env_backup


# ════════════════════════════════════════════════════════════
#  TC-2: stream_chat — 정상 GENERATION / STOP 청크
# ════════════════════════════════════════════════════════════

class TestOpenAIProviderStreamChat:
    def _get_provider_with_mock_stream(self, stream_chunks):
        """스트림 청크를 주입한 OpenAIProvider 반환."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id="gpt-5")
        p._client = MagicMock()
        p._client.chat.completions.create.return_value = iter(stream_chunks)
        return p

    def test_generation_chunks_yielded(self):
        """텍스트 delta가 있는 청크는 GENERATION 이벤트로 yield된다."""
        chunks = [
            _make_stream_chunk(content="안"),
            _make_stream_chunk(content="녕"),
            _make_stream_chunk(content="하세요"),
        ]
        p = self._get_provider_with_mock_stream(chunks)
        events = list(p.stream_chat("system", "user"))
        gen_events = [e for e in events if e["type"] == "GENERATION"]
        assert len(gen_events) == 3
        assert gen_events[0]["text"] == "안"
        assert gen_events[2]["text"] == "하세요"

    def test_stop_event_last(self):
        """STOP 이벤트가 마지막에 yield되고 완성 텍스트를 포함한다."""
        chunks = [
            _make_stream_chunk(content="테스트"),
            _make_stream_chunk(content="입니다"),
        ]
        p = self._get_provider_with_mock_stream(chunks)
        events = list(p.stream_chat("system", "user"))
        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        assert stop_events[0]["text"] == "테스트입니다"

    def test_stop_event_has_tokens_key(self):
        """STOP 이벤트에 tokens 딕셔너리가 포함된다."""
        chunks = [_make_stream_chunk(content="ok")]
        p = self._get_provider_with_mock_stream(chunks)
        events = list(p.stream_chat("system", "user"))
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert "tokens" in stop_event
        assert "input" in stop_event["tokens"]
        assert "output" in stop_event["tokens"]

    def test_no_generation_when_content_none(self):
        """delta.content가 None인 청크는 GENERATION 이벤트를 yield하지 않는다."""
        chunks = [
            _make_stream_chunk(content=None),
            _make_stream_chunk(content="텍스트"),
        ]
        p = self._get_provider_with_mock_stream(chunks)
        events = list(p.stream_chat("system", "user"))
        gen_events = [e for e in events if e["type"] == "GENERATION"]
        assert len(gen_events) == 1

    def test_empty_stream_gives_stop_with_empty_text(self):
        """청크가 없는 스트림 → STOP에 빈 텍스트."""
        p = self._get_provider_with_mock_stream([])
        events = list(p.stream_chat("system", "user"))
        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        assert stop_events[0]["text"] == ""


# ════════════════════════════════════════════════════════════
#  reasoning_effort — 모델 계열별 지원값 (2026-09-29 실측)
#  gpt-5 는 'none' 을, gpt-5.4-mini 는 'minimal' 을 400 으로 거부한다.
#  재생성 폴백(gpt-5.4-mini)이 minimal 을 받아 매번 400 → 사과문이 됐다.
# ════════════════════════════════════════════════════════════

_UNSUPPORTED_MINIMAL = (
    "Error code: 400 - {'error': {'message': \"Unsupported value: 'reasoning_effort' does not "
    "support 'minimal' with this model. Supported values are: 'none', 'low', 'medium', 'high', "
    "and 'xhigh'.\", 'type': 'invalid_request_error', 'param': 'reasoning_effort', "
    "'code': 'unsupported_value'}}"
)


def _provider(model_id):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.OpenAI"):
            from llm_router import OpenAIProvider
            p = OpenAIProvider(model_id=model_id)
    p._client = MagicMock()
    return p


class TestReasoningEffort:
    def setup_method(self):
        import llm_router
        llm_router._EFFORTS_LEARNED.clear()

    def test_fastest_step_maps_per_family(self):
        from llm_router import resolve_reasoning_effort as r
        assert r("gpt-5", "minimal") == "minimal"
        assert r("gpt-5", "none") == "minimal"
        assert r("gpt-5-mini", "minimal") == "minimal"
        assert r("gpt-5.4-mini", "minimal") == "none"
        assert r("gpt-5.4-mini", "none") == "none"
        assert r("gpt-5.5", "minimal") == "none"

    def test_other_steps_kept_or_nearest(self):
        from llm_router import resolve_reasoning_effort as r
        assert r("gpt-5.4-mini", "low") == "low"
        assert r("gpt-5", "xhigh") == "high"
        assert r("gpt-5.4-mini", "xhigh") == "xhigh"
        assert r("gpt-5.4-mini", "bogus") == "none"     # 알 수 없는 값 → 가장 빠른 단계

    def test_env_default_used(self):
        from llm_router import resolve_reasoning_effort as r
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            assert r("gpt-5.4-mini") == "none"
            assert r("gpt-5") == "minimal"

    def test_fallback_model_request_sends_none(self):
        p = _provider("gpt-5.4-mini")
        p._client.chat.completions.create.return_value = iter([])
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            list(p.stream_chat("s", "u"))
        assert p._client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "none"

    def test_unsupported_value_400_retried_once_with_learned_value(self):
        """표가 틀려도(모델이 지원값을 바꿔도) 400 메시지의 지원값으로 한 번 다시 보낸다."""
        p = _provider("gpt-5")                      # 표상 minimal 을 받는 계열
        p._client.chat.completions.create.side_effect = [Exception(_UNSUPPORTED_MINIMAL), iter([])]
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            events = list(p.stream_chat("s", "u"))
        calls = p._client.chat.completions.create.call_args_list
        assert [c.kwargs["reasoning_effort"] for c in calls] == ["minimal", "none"]
        assert events[-1]["type"] == "STOP"
        from llm_router import resolve_reasoning_effort
        assert resolve_reasoning_effort("gpt-5", "minimal") == "none"   # 이후 호출은 처음부터 맞춘다

    def test_other_errors_not_retried(self):
        p = _provider("gpt-5.4-mini")
        p._client.chat.completions.create.side_effect = Exception("rate limit")
        events = list(p.stream_chat("s", "u"))
        assert p._client.chat.completions.create.call_count == 1
        assert events[-1]["type"] == "ERROR"


# ════════════════════════════════════════════════════════════
#  reasoning_effort 400 재시도 — SDK 가 실제로 던지는 openai.BadRequestError 로
#  stream_chat 전체 경로를 본다. create() 는 스트리밍 전에 400 을 던지므로
#  다시 보내도 이미 나간 출력이 없다.
# ════════════════════════════════════════════════════════════

def _bad_request(message):
    """openai SDK 의 400 예외. str() 은 Cloud Run 로그에 찍힌 형식 그대로."""
    import httpx
    import openai
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.BadRequestError(message, response=httpx.Response(400, request=req), body=None)


def _efforts_sent(p):
    return [c.kwargs.get("reasoning_effort") for c in p._client.chat.completions.create.call_args_list]


class TestReasoningEffortRetry:
    def setup_method(self):
        import llm_router
        llm_router._EFFORTS_LEARNED.clear()

    def test_minimal_rejected_retried_with_none_and_streams(self):
        """'minimal' 400 → 'none' 으로 한 번 다시 보내고 그 스트림이 그대로 나간다.
        표가 minimal 을 받는다고 보는 gpt-5 로 재현 — gpt-5.4-mini 가 조용히 바뀐 것과 같은 상황."""
        p = _provider("gpt-5")
        p._client.chat.completions.create.side_effect = [
            _bad_request(_UNSUPPORTED_MINIMAL),
            iter([_make_stream_chunk(content="재생성"), _make_stream_chunk(content=" 답변")]),
        ]
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            events = list(p.stream_chat("s", "u"))
        assert _efforts_sent(p) == ["minimal", "none"]
        assert [e["text"] for e in events if e["type"] == "GENERATION"] == ["재생성", " 답변"]
        assert events[-1]["type"] == "STOP"
        assert events[-1]["text"] == "재생성 답변"
        assert not any(e["type"] == "ERROR" for e in events)

    def test_none_not_supported_retried_with_low(self):
        """지원값에 'none' 이 없으면 그다음으로 빠른 'low'."""
        p = _provider("gpt-5")
        msg = _UNSUPPORTED_MINIMAL.replace(
            "'none', 'low', 'medium', 'high', and 'xhigh'", "'low', 'medium', and 'high'")
        assert "'none'" not in msg
        p._client.chat.completions.create.side_effect = [
            _bad_request(msg), iter([_make_stream_chunk(content="ok")])]
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            events = list(p.stream_chat("s", "u"))
        assert _efforts_sent(p) == ["minimal", "low"]
        assert events[-1]["type"] == "STOP" and events[-1]["text"] == "ok"

    def test_model_accepting_minimal_sends_once(self):
        """minimal 을 받는 모델(메인 경로 gpt-5)은 한 번에 보낸다 — 메인 경로 지연 그대로."""
        p = _provider("gpt-5")
        p._client.chat.completions.create.return_value = iter([_make_stream_chunk(content="답변")])
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            events = list(p.stream_chat("s", "u"))
        assert _efforts_sent(p) == ["minimal"]
        assert events[-1]["type"] == "STOP" and events[-1]["text"] == "답변"

    def test_unrelated_400_not_retried(self):
        """reasoning_effort 와 무관한 400 은 다시 보내지 않고 예전처럼 ERROR 하나."""
        p = _provider("gpt-5.4-mini")
        err = _bad_request(
            "Error code: 400 - {'error': {'message': \"Invalid 'messages[1].content': string too "
            "long.\", 'type': 'invalid_request_error', 'param': 'messages[1].content', "
            "'code': 'string_above_max_length'}}")
        p._client.chat.completions.create.side_effect = err
        events = list(p.stream_chat("s", "u"))
        assert p._client.chat.completions.create.call_count == 1
        assert events == [{"type": "ERROR", "message": str(err)}]

    def test_reasoning_effort_400_without_supported_values_not_retried(self):
        """reasoning_effort 를 말해도 지원값 목록이 없으면 고를 값이 없어 다시 보내지 않는다."""
        p = _provider("gpt-5")
        p._client.chat.completions.create.side_effect = _bad_request(
            "Error code: 400 - {'error': {'message': \"Unsupported parameter: 'reasoning_effort' "
            "is not supported with this model.\", 'type': 'invalid_request_error', "
            "'param': 'reasoning_effort', 'code': 'unsupported_parameter'}}")
        events = list(p.stream_chat("s", "u"))
        assert p._client.chat.completions.create.call_count == 1
        assert events[-1]["type"] == "ERROR"

    def test_retry_rejected_again_stops_with_error(self):
        """다시 보낸 값도 400 이면 거기서 멈추고 ERROR — 재시도는 한 번뿐."""
        p = _provider("gpt-5")
        p._client.chat.completions.create.side_effect = [
            _bad_request(_UNSUPPORTED_MINIMAL),
            _bad_request(_UNSUPPORTED_MINIMAL.replace("support 'minimal'", "support 'none'")),
        ]
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            events = list(p.stream_chat("s", "u"))
        assert _efforts_sent(p) == ["minimal", "none"]
        assert events[-1]["type"] == "ERROR"

    def test_learned_value_sent_first_by_next_provider(self):
        """400 은 모델당 한 번 — 재생성마다 새로 만드는 provider 도 배운 값으로 바로 보낸다."""
        first = _provider("gpt-5")
        first._client.chat.completions.create.side_effect = [
            _bad_request(_UNSUPPORTED_MINIMAL), iter([])]
        second = _provider("gpt-5")
        second._client.chat.completions.create.return_value = iter([])
        with patch.dict(os.environ, {"LLM_REASONING_EFFORT": "minimal"}):
            list(first.stream_chat("s", "u"))
            list(second.stream_chat("s", "u"))
        assert _efforts_sent(first) == ["minimal", "none"]
        assert _efforts_sent(second) == ["none"]


# ════════════════════════════════════════════════════════════
#  TC-3: stream_chat — 오류 시 ERROR 청크
# ════════════════════════════════════════════════════════════

class TestOpenAIProviderError:
    def test_api_exception_yields_error_event(self):
        """OpenAI API 예외 발생 시 ERROR 이벤트가 yield된다."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id="gpt-5")
        p._client = MagicMock()
        p._client.chat.completions.create.side_effect = Exception("API 에러")
        events = list(p.stream_chat("system", "user"))
        assert any(e["type"] == "ERROR" for e in events)
        error_event = next(e for e in events if e["type"] == "ERROR")
        assert "API 에러" in error_event["message"]

    def test_error_event_has_message_key(self):
        """ERROR 이벤트에 message 키가 포함된다."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id="gpt-5")
        p._client = MagicMock()
        p._client.chat.completions.create.side_effect = RuntimeError("네트워크 오류")
        events = list(p.stream_chat("system", "user"))
        error_events = [e for e in events if e["type"] == "ERROR"]
        assert len(error_events) == 1
        assert "message" in error_events[0]


# ════════════════════════════════════════════════════════════
#  TC-5: stream_chat — usage 토큰 파싱
# ════════════════════════════════════════════════════════════

class TestOpenAIProviderTokens:
    def test_usage_tokens_captured(self):
        """usage.prompt_tokens, completion_tokens가 STOP의 tokens에 반영된다."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id="gpt-5")
        # 마지막 청크에 usage 첨부
        chunk_with_usage = _make_stream_chunk(
            content="응답",
            prompt_tokens=100,
            completion_tokens=50,
        )
        p._client = MagicMock()
        p._client.chat.completions.create.return_value = iter([chunk_with_usage])
        events = list(p.stream_chat("system", "user"))
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["tokens"]["input"] == 100
        assert stop_event["tokens"]["output"] == 50

    def test_no_usage_gives_zero_tokens(self):
        """usage 없는 스트림 → tokens {"input": 0, "output": 0}."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import OpenAIProvider
                p = OpenAIProvider(model_id="gpt-5")
        chunks = [_make_stream_chunk(content="ok")]
        p._client = MagicMock()
        p._client.chat.completions.create.return_value = iter(chunks)
        events = list(p.stream_chat("system", "user"))
        stop_event = next(e for e in events if e["type"] == "STOP")
        assert stop_event["tokens"]["input"] == 0
        assert stop_event["tokens"]["output"] == 0


# ════════════════════════════════════════════════════════════
#  TC-6: get_llm_provider 팩토리
# ════════════════════════════════════════════════════════════

def _patch_openai_and_call(fn, *args, env_extras=None, **kwargs):
    """openai.OpenAI를 mock 하여 fn을 호출하는 헬퍼."""
    env = {"OPENAI_API_KEY": "test-key"}
    if env_extras:
        env.update(env_extras)
    import openai as _openai
    original_cls = _openai.OpenAI
    _openai.OpenAI = MagicMock(return_value=MagicMock())
    try:
        with patch.dict(os.environ, env):
            return fn(*args, **kwargs)
    finally:
        _openai.OpenAI = original_cls


class TestGetLLMProvider:
    def test_default_returns_openai_gpt5(self):
        """provider_id=None, 환경변수 없으면 openai_gpt5 반환."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            os.environ.pop("RAG_LLM_DEFAULT_PROVIDER", None)
        from llm_router import get_llm_provider
        p = _patch_openai_and_call(get_llm_provider)
        assert p.provider_id == "openai_gpt5"
        assert p.model_id == "gpt-5"

    def test_explicit_provider_id(self):
        """명시적 provider_id='openai_gpt5_mini' → gpt-5-mini."""
        from llm_router import get_llm_provider
        p = _patch_openai_and_call(get_llm_provider, "openai_gpt5_mini")
        assert p.model_id == "gpt-5-mini"

    def test_env_var_default_provider(self):
        """RAG_LLM_DEFAULT_PROVIDER 환경변수가 우선 적용된다."""
        from llm_router import get_llm_provider
        p = _patch_openai_and_call(
            get_llm_provider,
            env_extras={"RAG_LLM_DEFAULT_PROVIDER": "openai_gpt5_mini"},
        )
        assert p.model_id == "gpt-5-mini"

    def test_returns_llm_provider_instance(self):
        """반환값이 LLMProvider 추상 클래스의 인스턴스다."""
        from llm_router import get_llm_provider, LLMProvider
        p = _patch_openai_and_call(get_llm_provider, "openai_gpt5")
        assert isinstance(p, LLMProvider)


# ════════════════════════════════════════════════════════════
#  TC-7: get_llm_provider — 알 수 없는 provider_id
# ════════════════════════════════════════════════════════════

class TestGetLLMProviderUnknown:
    def test_unknown_provider_raises_value_error(self):
        """알 수 없는 provider_id → ValueError 발생."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from llm_router import get_llm_provider
            with pytest.raises(ValueError, match="Unknown"):
                get_llm_provider("anthropic_claude_3")

    def test_empty_provider_id_raises(self):
        """빈 문자열 provider_id → ValueError 발생."""
        from llm_router import get_llm_provider
        with pytest.raises((ValueError, AttributeError)):
            get_llm_provider("")


# ════════════════════════════════════════════════════════════
#  TC-8: get_fallback_provider
# ════════════════════════════════════════════════════════════

class TestGetFallbackProvider:
    def test_fallback_returns_gpt5_mini(self):
        """환경변수 없을 때 기본 fallback 모델(gpt-5.4-mini) 반환."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            os.environ.pop("RAG_LLM_FALLBACK_MODEL", None)
            with patch("openai.OpenAI"):
                from llm_router import get_fallback_provider
                p = get_fallback_provider()
        assert p.model_id == "gpt-5.4-mini"

    def test_fallback_env_override(self):
        """RAG_LLM_FALLBACK_MODEL 환경변수로 모델 변경 가능."""
        env = {"OPENAI_API_KEY": "test-key", "RAG_LLM_FALLBACK_MODEL": "gpt-5"}
        with patch.dict(os.environ, env):
            with patch("openai.OpenAI"):
                from llm_router import get_fallback_provider
                p = get_fallback_provider()
        assert p.model_id == "gpt-5"

    def test_fallback_is_llm_provider(self):
        """반환값이 LLMProvider 인스턴스다."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                from llm_router import get_fallback_provider, LLMProvider
                p = get_fallback_provider()
        assert isinstance(p, LLMProvider)


# ════════════════════════════════════════════════════════════
#  TC-통합: @pytest.mark.integration (실제 OpenAI API 필요)
# ════════════════════════════════════════════════════════════

_needs_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — integration tests skipped",
)


@pytest.mark.integration
@_needs_openai
class TestIntegration:
    def test_openai_provider_stream(self):
        """실제 OpenAI API로 스트리밍 검증 (gpt-5-mini 사용 — 비용 최소화)."""
        from llm_router import OpenAIProvider
        # gpt-5 대신 gpt-5-mini로 비용 절감
        model = os.environ.get("RAG_LLM_FALLBACK_MODEL", "gpt-5-mini")
        p = OpenAIProvider(model_id=model)
        events = list(p.stream_chat("당신은 의료 정보 AI입니다.", "두통의 일반적 원인은?", max_tokens=50))
        assert any(e["type"] == "GENERATION" for e in events)
        stop_events = [e for e in events if e["type"] == "STOP"]
        assert len(stop_events) == 1
        assert len(stop_events[0]["text"]) > 0
