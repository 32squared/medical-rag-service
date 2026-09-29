"""
LLM 추상화 + OpenAI Provider (Phase 1).
Anthropic/Vertex는 Phase 3에서 추가.

주요 클래스:
  LLMProvider         — 추상 기본 인터페이스
  OpenAIProvider      — OpenAI GPT 구현체
  get_llm_provider()  — 프로바이더 팩토리 (환경변수 기반)
  get_fallback_provider() — 재생성용 저비용 모델 (gpt-5.4-mini)
"""

import os
import re
import time
import logging
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Optional

logger = logging.getLogger(__name__)

# llm_providers 테이블 id 매핑 표 (고정 매핑)
# Phase 1 공식 provider_id → model_id 매핑
_PROVIDER_ID_TO_MODEL: Dict[str, str] = {
    "openai_gpt5": "gpt-5",
    "openai_gpt5_mini": "gpt-5-mini",
    "openai_gpt5_4": "gpt-5.4",
    "openai_gpt5_4_mini": "gpt-5.4-mini",
    "openai_gpt5_4_nano": "gpt-5.4-nano",
    "openai_gpt5_5": "gpt-5.5",
}


# reasoning_effort 지원값은 모델 계열마다 다르다(2026-09-29 실측, 400 메시지 원문 기준):
#   gpt-5 · gpt-5-mini · gpt-5-nano  → minimal / low / medium / high        ('none' 은 400)
#   gpt-5.1 이후(gpt-5.4-mini 등)     → none / low / medium / high / xhigh  ('minimal' 은 400)
# 가장 빠른 단계의 이름이 계열마다 달라(minimal·none) 설정값을 모델에 맞춰 바꾼다.
# 이 차이로 재생성 폴백(gpt-5.4-mini)이 매번 400 → 사과문이 됐다.
_EFFORT_ORDER = ("none", "minimal", "low", "medium", "high", "xhigh")
_EFFORTS_GPT5_0 = ("minimal", "low", "medium", "high")
_EFFORTS_GPT5_X = ("none", "low", "medium", "high", "xhigh")
# 400 메시지에서 알게 된 모델별 지원값(프로세스 수명) — 위 표가 틀려도 모델당 한 번만 실패한다.
_EFFORTS_LEARNED: Dict[str, tuple] = {}


def _supported_efforts(model_id: str) -> tuple:
    mid = model_id.lower()
    if mid in _EFFORTS_LEARNED:
        return _EFFORTS_LEARNED[mid]
    if re.match(r"gpt-5\.\d", mid):
        return _EFFORTS_GPT5_X
    return _EFFORTS_GPT5_0


def resolve_reasoning_effort(model_id: str, requested: Optional[str] = None) -> str:
    """요청 단계(기본 env LLM_REASONING_EFFORT)를 모델이 받는 값 중 가장 가까운 것으로.

    같은 거리면 더 빠른 쪽 — minimal 은 gpt-5.x 에서 none, none 은 gpt-5 에서 minimal.
    알 수 없는 값은 가장 빠른 단계로 본다.
    """
    req = (requested or os.environ.get("LLM_REASONING_EFFORT", "minimal")).lower()
    sup = _supported_efforts(model_id)
    if req in sup:
        return req
    if req not in _EFFORT_ORDER:
        req = "minimal"
    i = _EFFORT_ORDER.index(req)
    return min(sup, key=lambda e: (abs(_EFFORT_ORDER.index(e) - i), _EFFORT_ORDER.index(e)))


def _learn_efforts_from_error(model_id: str, err: Exception) -> bool:
    """reasoning_effort 미지원 400 이면 메시지의 지원값을 기억하고 True."""
    msg = str(err)
    if "reasoning_effort" not in msg or "Supported values are" not in msg:
        return False
    tail = msg.split("Supported values are", 1)[1].split(".", 1)[0]
    vals = tuple(v for v in re.findall(r"'([a-z]+)'", tail) if v in _EFFORT_ORDER)
    if not vals:
        return False
    _EFFORTS_LEARNED[model_id.lower()] = vals
    logger.warning("[LLMRouter] %s reasoning_effort 지원값 갱신: %s", model_id, vals)
    return True


def _model_id_to_provider_suffix(model_id: str) -> str:
    """
    model_id → provider_id suffix 변환.

    규칙:
      - 역매핑 테이블 우선 조회
      - 없으면 하이픈 제거/변환: "gpt-5" → "gpt5", "gpt-5-mini" → "gpt5_mini"
        (숫자 앞 하이픈 제거, 알파벳 앞 하이픈은 언더스코어)
    """
    # 역매핑 테이블 우선
    for pid, mid in _PROVIDER_ID_TO_MODEL.items():
        if mid == model_id:
            return pid[len("openai_"):]  # suffix만 반환

    # 규칙 기반 변환
    import re as _re
    # "gpt-5" → "gpt5" (숫자 앞 하이픈 제거)
    s = _re.sub(r'-(\d)', r'\1', model_id)
    # 나머지 하이픈은 언더스코어
    s = s.replace("-", "_")
    return s


def _provider_suffix_to_model_id(suffix: str) -> str:
    """
    provider_id suffix → model_id 변환.

    예: "gpt5" → "gpt-5",  "gpt5_mini" → "gpt-5-mini"
    매핑 테이블 우선, 없으면 규칙 기반.
    """
    # 매핑 테이블에서 직접 조회
    pid = "openai_" + suffix
    if pid in _PROVIDER_ID_TO_MODEL:
        return _PROVIDER_ID_TO_MODEL[pid]

    # 규칙: 숫자 앞에 하이픈 삽입, 언더스코어를 하이픈으로
    import re as _re
    s = _re.sub(r'(\D)(\d)', r'\1-\2', suffix)
    s = s.replace("_", "-")
    return s


# ════════════════════════════════════════════════════════════
#  추상 인터페이스
# ════════════════════════════════════════════════════════════

class LLMProvider(ABC):
    """LLM 프로바이더 추상 기본 클래스."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """llm_providers 테이블 id 컬럼과 매핑되는 식별자."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """실제 모델 식별자 (예: 'gpt-5', 'gpt-5-mini')."""
        ...

    @abstractmethod
    def stream_chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> Iterator[Dict]:
        """
        SSE 호환 청크를 yield한다.

        Yields:
            {"type": "GENERATION", "text": "...delta..."}
            {"type": "STOP", "text": "(완성 응답)", "tokens": {"input": N, "output": N}}
            {"type": "ERROR", "message": "..."}
        """
        ...


# ════════════════════════════════════════════════════════════
#  OpenAI 구현체
# ════════════════════════════════════════════════════════════

class OpenAIProvider(LLMProvider):
    """
    OpenAI chat completions 스트리밍 프로바이더.

    gpt-5.4 계열(메인/재생성) 지원. (gpt-5/gpt-5-mini는 단가표 은퇴 — 마이그레이션)
    환경변수:
        RAG_LLM_MODEL           — 기본 메인 모델 (기본값: gpt-5.4-mini)
        RAG_LLM_FALLBACK_MODEL  — 재생성용 모델 (기본값: gpt-5.4-mini)
        OPENAI_API_KEY          — 필수
    """

    def __init__(self, model_id: str = None, api_key: str = None):
        from openai import OpenAI
        self._model_id = model_id or os.environ.get("RAG_LLM_MODEL", "gpt-5.4-mini")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self._client = OpenAI(api_key=self._api_key)
        # provider_id: "gpt-5" → "openai_gpt5",  "gpt-5-mini" → "openai_gpt5_mini"
        # 숫자와 문자 사이 하이픈은 제거, 단어 구분 하이픈은 언더스코어로 변환
        # 규칙: gpt-N → gptN, 이후 나머지 단어 구분은 _
        # "gpt-5" → remove hyphen between word and digit → "gpt5"
        # "gpt-5-mini" → "gpt5_mini"
        clean = _model_id_to_provider_suffix(self._model_id)
        self._provider_id = "openai_" + clean

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def stream_chat(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> Iterator[Dict]:
        """
        OpenAI chat completions 스트리밍.

        GPT-5는 신규 모델이라 chunk.usage 지원 여부가 불확실 — 방어적으로 처리.
        스트리밍 종료 후 STOP 이벤트를 yield한다.
        """
        try:
            # GPT-5, o1, o3, o4 계열은 신규 API 규칙:
            #   - max_tokens 거부 → max_completion_tokens 사용
            #   - temperature 1.0만 허용 → 파라미터 전송 안 함 (기본값 1 사용)
            # gpt-4o, gpt-4 등 구형은 기존 규칙 유지
            mid = self._model_id.lower()
            is_new_api = (
                mid.startswith("gpt-5")
                or mid.startswith("o1")
                or mid.startswith("o3")
                or mid.startswith("o4")
            )
            params = {
                "model": self._model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": True,
                # GPT-5 등 신규 모델은 stream_options로 usage 포함 명시 필요
                "stream_options": {"include_usage": True},
            }
            if is_new_api:
                # GPT-5는 reasoning tokens가 max_completion_tokens에 포함됨.
                # 2048이면 reasoning에 다 쓰여서 응답이 비는 경우 발생.
                # 8192로 늘리고, reasoning_effort는 가장 빠른 단계로 응답 우선.
                params["max_completion_tokens"] = max(max_tokens * 4, 8192)
                # 대화형 RAG는 속도 우선 → LLM_REASONING_EFFORT=minimal 권장(첫 토큰 전
                # 추론지연 최소화, 실측 12.75s→~1s). 배치 평가 등 품질 우선은 low/medium.
                # 모델마다 받는 값이 달라 resolve_reasoning_effort 가 맞춘다(위 표).
                if mid.startswith("gpt-5"):
                    params["reasoning_effort"] = resolve_reasoning_effort(self._model_id)
                # temperature는 1.0만 허용 — 명시적으로 보내지 않음 (기본 1)
            else:
                params["max_tokens"] = max_tokens
                params["temperature"] = temperature

            try:
                stream = self._client.chat.completions.create(**params)
            except Exception as e:
                # 지원값이 조용히 바뀌는 모델이 있다(gpt-5.4-mini 가 minimal 을 거부) —
                # 400 이 알려 준 지원값으로 한 번만 다시 보낸다.
                if "reasoning_effort" in params and _learn_efforts_from_error(self._model_id, e):
                    params["reasoning_effort"] = resolve_reasoning_effort(self._model_id)
                    stream = self._client.chat.completions.create(**params)
                else:
                    raise
            full = ""
            input_tokens = 0
            output_tokens = 0

            for chunk in stream:
                # choices가 없는 청크(usage-only 청크 등) 방어
                delta_text = None
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and hasattr(delta, "content") and delta.content:
                        delta_text = delta.content

                if delta_text:
                    full += delta_text
                    yield {"type": "GENERATION", "text": delta_text}

                # usage 정보 — GPT-5에서는 마지막 청크에 포함될 수 있음
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    usage = chunk.usage
                    if hasattr(usage, "prompt_tokens") and usage.prompt_tokens:
                        input_tokens = int(usage.prompt_tokens)
                    if hasattr(usage, "completion_tokens") and usage.completion_tokens:
                        output_tokens = int(usage.completion_tokens)

            yield {
                "type": "STOP",
                "text": full,
                "tokens": {"input": input_tokens, "output": output_tokens},
            }

        except Exception as e:
            logger.error("[LLMRouter] OpenAI 스트리밍 오류: %s", e)
            yield {"type": "ERROR", "message": str(e)}


# ════════════════════════════════════════════════════════════
#  팩토리 함수
# ════════════════════════════════════════════════════════════

def get_llm_provider(provider_id: str = None) -> LLMProvider:
    """
    llm_providers 테이블에서 활성 프로바이더를 조회해 반환한다.

    Phase 1에서는 환경변수 기반 폴백.
    T7 완료 후 DB 동적 조회로 전환 가능 (인터페이스 동일).

    Args:
        provider_id: llm_providers.id 값 (None이면 환경변수 RAG_LLM_DEFAULT_PROVIDER 참조)

    Returns:
        LLMProvider 인스턴스

    Raises:
        ValueError: 알 수 없는 provider_id
    """
    if provider_id is None:
        provider_id = os.environ.get("RAG_LLM_DEFAULT_PROVIDER", "openai_gpt5")

    if provider_id.startswith("openai_"):
        # 매핑 테이블 우선, 없으면 규칙 기반 역변환
        suffix = provider_id[len("openai_"):]
        model_id = _provider_suffix_to_model_id(suffix)
        logger.debug("[LLMRouter] provider=%s → model_id=%s", provider_id, model_id)
        return OpenAIProvider(model_id=model_id)

    raise ValueError(f"Unknown LLM provider_id: {provider_id!r}")


def get_fallback_provider() -> LLMProvider:
    """
    가드레일 재생성용 저비용 모델 프로바이더를 반환한다.

    기본: gpt-5.4-mini (환경변수 RAG_LLM_FALLBACK_MODEL로 재정의 가능).
    사용자 정상 응답은 get_llm_provider()를 사용할 것.
    """
    model_id = os.environ.get("RAG_LLM_FALLBACK_MODEL", "gpt-5.4-mini")
    logger.debug("[LLMRouter] fallback provider model_id=%s", model_id)
    return OpenAIProvider(model_id=model_id)
