"""
korean_tokenizer.py — 한국어 의미 토큰화 (Sprint 2, 도달률 본수선).

기존 휴리스틱(_korean_meaningful_tokens: 조사·어미 근사 제거)의 한계는
"머리가 아파요" 같이 띄어쓰고 활용된 구어체를 잡지 못하는 것이다.
이 모듈은 Kiwi 형태소 분석기가 설치돼 있으면 명사/동사/형용사 어간을 추출하고,
없으면 기존 휴리스틱으로 자동 폴백한다(무해 — import 실패가 검색을 막지 않는다).

핵심: 검색 sparse 토큰화와 증상 매칭(symptom_matcher)이 *동일한* 정규화를
공유하게 만들어, "머리가 아파요" → [머리, 아프] → 증상 동의어 인덱스 도달.

tokenize()는 Kiwi 유무와 무관하게 항상 list[str]를 반환한다.
backend()로 현재 사용 중인 백엔드('kiwi'|'heuristic')를 확인할 수 있다(평가·디버그용).
"""

from __future__ import annotations

import logging
import os
import re
from typing import List

logger = logging.getLogger(__name__)

# 환경변수로 강제 비활성(폴백) 가능 — 회귀 시 즉시 끄기 위한 안전판
_DISABLE_KIWI = os.environ.get("DISABLE_KIWI", "").lower() in ("1", "true", "yes")

_kiwi = None
_kiwi_tried = False

# Kiwi가 추출할 의미 품사 (명사·동사·형용사·어근·외국어/영문)
_KIWI_MEANINGFUL_TAGS = {
    "NNG", "NNP", "NNB",        # 명사
    "VV", "VA",                  # 동사·형용사 (어간)
    "XR",                        # 어근
    "SL", "SH", "SN",            # 외국어·한자·숫자
    "MAG",                       # 일반부사 (일부 증상 표현)
}

# 형태소 어간 중 제거할 기능성 토큰
_KIWI_STOP = {
    "있", "없", "하", "되", "그", "이", "저", "것", "수", "때", "좀", "잘",
    "안", "못", "또", "더", "같", "보", "오", "주", "지", "들",
}


def _get_kiwi():
    """Kiwi 인스턴스 lazy 로드. 미설치/비활성 시 None."""
    global _kiwi, _kiwi_tried
    if _kiwi_tried:
        return _kiwi
    _kiwi_tried = True
    if _DISABLE_KIWI:
        logger.info("[tokenizer] DISABLE_KIWI=1 — 휴리스틱 폴백 사용")
        return None
    try:
        from kiwipiepy import Kiwi  # type: ignore
        _kiwi = Kiwi()
        logger.info("[tokenizer] Kiwi 형태소 분석기 활성화")
    except Exception as e:
        logger.info("[tokenizer] Kiwi 미설치/로드 실패 — 휴리스틱 폴백: %s", e)
        _kiwi = None
    return _kiwi


def backend() -> str:
    """현재 토큰화 백엔드: 'kiwi' 또는 'heuristic'."""
    return "kiwi" if _get_kiwi() is not None else "heuristic"


# ── 휴리스틱 폴백 (기존 rag_engine._korean_meaningful_tokens 로직 복제) ──
_PARTICLE_RE = re.compile(
    r"(?:으로|에서|에게|까지|부터|이라고|라고|이며|하고|하며|되면|되어|이고|"
    r"이랑|랑|이나|한테|처럼|마다|밖에|"
    r"입니다|습니다|어요|아요|예요|네요|은|는|이|가|을|를|에|의|도|만|과|와|로|요|고|며|서|들|임|함)$"
)
_HEUR_STOP = {
    "것", "수", "등", "때", "더", "좀", "잘", "안", "못", "또", "그", "저", "거", "게", "걸",
    "점", "중", "및", "약간", "정도", "관련", "경우", "무엇", "어떻게", "어떤", "있는", "있어요",
    "있나요", "같아요", "같은", "너무", "자꾸", "계속", "갑자기", "요즘", "오늘", "어제", "정말",
}
_CLEAN_RE = re.compile(r"[^\w\s가-힣a-zA-Z0-9]")


def _heuristic_tokens(query: str, max_tokens: int) -> List[str]:
    clean = _CLEAN_RE.sub(" ", query or "")
    out: List[str] = []
    for tok in clean.split():
        t = _PARTICLE_RE.sub("", tok)
        if len(t) >= 2 and t not in _HEUR_STOP and t not in out:
            out.append(t)
        if len(out) >= max_tokens:
            break
    return out


def _kiwi_tokens(kiwi, query: str, max_tokens: int) -> List[str]:
    out: List[str] = []
    try:
        tokens = kiwi.tokenize(query or "")
    except Exception as e:
        logger.warning("[tokenizer] Kiwi 분석 실패 — 휴리스틱 폴백: %s", e)
        return _heuristic_tokens(query, max_tokens)
    for tok in tokens:
        form = getattr(tok, "form", "")
        tag = getattr(tok, "tag", "")
        if tag not in _KIWI_MEANINGFUL_TAGS:
            continue
        if len(form) < 1 or form in _KIWI_STOP:
            continue
        # 동사/형용사 어간은 1글자도 의미(아프, 붓 등) — 명사는 1글자 제외
        if tag in ("NNG", "NNP", "NNB") and len(form) < 2:
            continue
        if form not in out:
            out.append(form)
        if len(out) >= max_tokens:
            break
    return out


def tokenize(query: str, max_tokens: int = 8) -> List[str]:
    """
    한국어 질의 → 의미 토큰 리스트. Kiwi 우선, 폴백 휴리스틱.

    Args:
        query:      사용자 질의
        max_tokens: 최대 토큰 수 (tsquery 폭발 방지)

    Returns:
        의미 토큰 리스트 (중복 없음)
    """
    kiwi = _get_kiwi()
    if kiwi is not None:
        toks = _kiwi_tokens(kiwi, query, max_tokens)
        if toks:
            return toks
        # Kiwi가 0개 반환(드묾) → 휴리스틱 보강
    return _heuristic_tokens(query, max_tokens)
