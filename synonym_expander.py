"""
synonym_expander.py — 의학용어 동의어 질의 확장 (KB 확장 P2-9).

medical_synonyms.json의 동의어 그룹을 로드해 sparse 검색 토큰을 확장한다.
"속쓰림" 질의가 "위산역류"로 적재된 KB 청크와 매칭되도록 recall을 보강하는
순수 검색 보조 — 의학적 판단·진단 의미는 부여하지 않는다.

설계:
- 1회 로드 캐시 (모듈 레벨), 파일 없음/파싱 실패 시 빈 사전으로 무해 동작.
- exact match만 확장 (부분 문자열 확장은 오확장 위험 — '열'→'발열' 그룹은
  그룹 정의 자체에 '열'을 포함시켜 해결).
- 확장 토큰 수 상한(_MAX_TOTAL_TOKENS)으로 tsquery 폭발 방지.

expand_tokens()은 순수 함수 — DB/네트워크 불필요, 로컬 테스트 가능.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

_SYNONYMS_FILENAME = "medical_synonyms.json"

# 확장 후 전체 토큰 수 상한 (원본 토큰 최대 6개 + 동의어)
_MAX_TOTAL_TOKENS = 14
# 토큰 1개당 추가되는 동의어 상한 (한 그룹이 비대해도 질의 독점 방지)
_MAX_SYNONYMS_PER_TOKEN = 3

# term(정규화) → 같은 그룹의 다른 term 리스트
_INDEX: Dict[str, List[str]] = {}
_LOADED = False


def _normalize(term: str) -> str:
    """매칭용 정규화: 공백 제거 + 소문자 (그룹 정의도 동일 규칙)."""
    return (term or "").replace(" ", "").lower()


def _load_index() -> Dict[str, List[str]]:
    """medical_synonyms.json → term 인덱스 (1회 로드, 실패 시 빈 dict)."""
    global _INDEX, _LOADED
    if _LOADED:
        return _INDEX
    _LOADED = True
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _SYNONYMS_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for group in data.get("groups", []):
            terms = [t for t in (group.get("terms") or []) if t]
            if len(terms) < 2:
                continue
            for t in terms:
                key = _normalize(t)
                others = [o for o in terms if _normalize(o) != key]
                # 같은 term이 여러 그룹에 있으면 합치되 중복 제거
                existing = _INDEX.get(key, [])
                for o in others:
                    if o not in existing:
                        existing.append(o)
                _INDEX[key] = existing
        logger.info("[synonym] %d개 그룹 로드 — 인덱스 %d terms",
                    len(data.get("groups", [])), len(_INDEX))
    except FileNotFoundError:
        logger.warning("[synonym] %s 없음 — 동의어 확장 비활성", _SYNONYMS_FILENAME)
    except Exception as e:
        logger.warning("[synonym] 로드 실패 (확장 비활성): %s", e)
    return _INDEX


def expand_tokens(tokens: List[str], max_total: int = _MAX_TOTAL_TOKENS) -> List[str]:
    """
    의미 토큰 리스트 → 동의어 확장 토큰 리스트 (순수 함수).

    원본 토큰 순서를 보존하고, 동의어는 뒤에 덧붙인다 (ILIKE fallback의
    AND 매칭은 원본 토큰 기준이므로 원본 우선 순서가 중요).

    Args:
        tokens:    _korean_meaningful_tokens() 산출 토큰
        max_total: 확장 후 전체 토큰 수 상한

    Returns:
        확장된 토큰 리스트 (중복 없음, 상한 적용)
    """
    if not tokens:
        return tokens
    index = _load_index()
    if not index:
        return tokens

    out = list(tokens)
    seen = {_normalize(t) for t in tokens}
    for tok in tokens:
        if len(out) >= max_total:
            break
        synonyms = index.get(_normalize(tok), [])
        added = 0
        for syn in synonyms:
            if added >= _MAX_SYNONYMS_PER_TOKEN or len(out) >= max_total:
                break
            key = _normalize(syn)
            if key in seen:
                continue
            out.append(syn)
            seen.add(key)
            added += 1
    return out


def synonyms_for(term: str) -> List[str]:
    """
    term이 속한 동의어 그룹의 전체 구성원 반환 (term 자신 포함, 캡 없음).

    expand_tokens()는 질의 확장용이라 토큰당 동의어 수에 상한이 있지만,
    증상 매칭 인덱스 구축 등에서는 그룹 전체가 필요하다 — 이 함수를 쓴다.
    """
    index = _load_index()
    key = _normalize(term)
    others = index.get(key)
    if others is None:
        return [term]
    return [term] + list(others)


def reload_synonyms() -> int:
    """동의어 사전 강제 재로드 (운영 중 JSON 갱신용). 인덱스 크기 반환."""
    global _INDEX, _LOADED
    _INDEX = {}
    _LOADED = False
    return len(_load_index())
