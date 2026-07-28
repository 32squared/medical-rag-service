"""
symptom_matcher.py — 질의 → 증상 키 매칭 (Sprint 1 도달률 본수선).

기존 rag_engine.detect_symptom_keys()는 *문진 질문 키워드*("지속/기간/고열")로만
매칭해서 "머리아파" 같은 증상 표현 자체를 두통(headache)에 연결하지 못했다.

이 모듈은 증상을 그 *이름·세부표현·동의어*로 인덱싱해 도달률을 높인다:
  surface term(증상명 "두통", detail "미열·고열", 동의어 "머리아파") → symptom_key

매칭 경로 (recall 우선, 다단):
  1. 카탈로그의 surface term이 query 안에 substring 으로 등장 (붙여쓴 구어체 커버)
  2. 형태소/휴리스틱 토큰이 surface term과 일치 (띄어쓴 구어체 일부 커버)
모두 동의어 확장으로 보강된다.

match_symptoms()는 (DB 없이) 순수 동작 — 카탈로그·동의어·토크나이저만 의존.
이 매칭 결과로 진료과(department)까지 노출할 수 있다(department_hint).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# surface term 최소 길이 (1글자 substring 오매칭 방지)
_MIN_TERM_LEN = 2

# surface term → symptom_key 역인덱스 (1회 구축)
_INDEX: Dict[str, str] = {}
_TERM_LIST: List[Tuple[str, str]] = []   # (term, symptom_key), 긴 term 우선 정렬
_BUILT = False


def _normalize(s: str) -> str:
    return (s or "").replace(" ", "").lower()


# 정도·빈도 부사(필러) — 증상 표면형 사이에 끼어 substring 매칭을 깨뜨린다.
# 예: "머리가 계속 아파요" → 동의어 "머리가아파"가 "머리가계속아파요"에서 미발견.
# 이 부사들을 제거하면 기존 표면형으로 도달한다. (reach: 부사삽입 내성)
# 주의: 1~2글자 필러는 증상어의 부분문자열을 깨뜨릴 수 있어 제외("막"→"결막염" 파손).
# 안전하게 제거 가능한, 증상어에 거의 등장하지 않는 정도·빈도 부사만 등록.
_FILLERS = [
    "계속해서", "계속", "자꾸만", "자꾸", "지속적으로", "꾸준히",
    "너무너무", "너무", "정말", "진짜", "되게", "엄청", "무척",
    "조금", "약간", "살짝", "심하게", "요즘", "요새", "최근에", "그냥",
]


def _strip_fillers(s: str) -> str:
    """정도·빈도 부사 제거 (증상 매칭 recall 보조). 분류기 안전신호와 무관."""
    out = s or ""
    for f in _FILLERS:
        out = out.replace(f, " ")
    return out


def _name_terms_for(item: dict) -> List[str]:
    """증상의 *대표* 표현 (symptom_name) — 동의어 확장 대상.
    detail은 동반증상을 포함할 수 있어 확장하면 오염되므로 분리한다."""
    terms: List[str] = []
    name = (item.get("symptom_name") or "").strip()
    if name:
        terms.append(name)
        if " " in name:                       # "가슴 통증" → "가슴통증"도
            terms.append(name.replace(" ", ""))
    return terms


def _detail_terms_for(item: dict) -> List[str]:
    """증상 세부표현 (detail) — 리터럴 인덱싱만(동의어 확장 안 함)."""
    out: List[str] = []
    for d in re.split(r"[,/·]", item.get("detail") or ""):
        d = d.strip()
        if d:
            out.append(d)
    return out


def _expand(term: str) -> List[str]:
    """surface term을 동의어 그룹 전체로 확장 (캡 없는 synonyms_for — 인덱스 완전성)."""
    try:
        from synonym_expander import synonyms_for
        return synonyms_for(term)
    except Exception:
        return [term]


def _build_index() -> None:
    global _INDEX, _TERM_LIST, _BUILT
    if _BUILT:
        return
    _BUILT = True
    index: Dict[str, str] = {}
    try:
        from symptom_catalog import load_catalog
        catalog = load_catalog()
    except Exception as e:
        logger.warning("[matcher] 카탈로그 로드 실패: %s", e)
        catalog = {}

    for key, item in catalog.items():
        # 대표 표현(symptom_name)만 동의어 확장 — detail은 리터럴(오염 방지)
        surfaces: List[str] = []
        for term in _name_terms_for(item):
            surfaces.extend(_expand(term))
        surfaces.extend(_detail_terms_for(item))
        for surface in surfaces:
            norm = _normalize(surface)
            if len(norm) < _MIN_TERM_LEN:
                continue
            # 같은 surface가 여러 증상에 매핑되면 먼저 등록된 것 유지
            index.setdefault(norm, key)
    _INDEX = index
    # 긴 term 우선(부분문자열 오매칭 시 더 구체적인 것 선택)
    _TERM_LIST = sorted(index.items(), key=lambda kv: -len(kv[0]))
    logger.info("[matcher] 증상 surface 인덱스 %d terms / %d 증상",
                len(index), len(catalog))


def match_symptoms(query: str, max_results: int = 4) -> List[str]:
    """
    질의 → 매칭된 symptom_key 리스트 (순수 함수, recall 우선).

    Args:
        query:       사용자 질의
        max_results: 최대 반환 증상 수

    Returns:
        symptom_key 리스트 (질의 내 등장 순서 보존, 중복 제거)
    """
    _build_index()
    if not query:
        return []
    # 정도·빈도 부사를 제거해 표면형 substring 매칭의 부사삽입 내성을 확보
    nq = _normalize(_strip_fillers(query))

    matched: List[str] = []
    matched_set = set()

    # 1) surface term substring 매칭 (긴 term 우선) — 붙여쓴 구어체 커버
    for term, key in _TERM_LIST:
        if key in matched_set:
            continue
        if term in nq:
            matched.append(key)
            matched_set.add(key)
            if len(matched) >= max_results:
                return matched

    # 2) 형태소/휴리스틱 토큰 ↔ surface term 일치 (띄어쓴 구어체 보조)
    try:
        from korean_tokenizer import tokenize
        tokens = tokenize(query)
    except Exception:
        tokens = []
    for tok in tokens:
        if len(matched) >= max_results:
            break
        ntok = _normalize(tok)
        if len(ntok) < _MIN_TERM_LEN:
            continue
        key = _INDEX.get(ntok)
        if key and key not in matched_set:
            matched.append(key)
            matched_set.add(key)

    return matched


def departments_for(symptom_keys: List[str]) -> List[str]:
    """증상 키 리스트 → 진료과 리스트 (순서 보존, 중복 제거)."""
    from symptom_catalog import department_for
    out: List[str] = []
    for k in symptom_keys:
        dept = department_for(k)
        if dept and dept not in out:
            out.append(dept)
    return out


def department_hint(query: str) -> Dict:
    """
    질의 → 진료과 안내 구조 (답변 배선용).

    Returns:
        {"symptom_keys": [...], "departments": [...], "hint": "안내 문장" | ""}
    의료법 안전: '일반적으로 ~과에서 진료' 정보 제공 — 진단 아님.
    응급 신호가 있으면 과 선택보다 119 우선 메시지를 병기한다.
    """
    keys = match_symptoms(query)
    depts = departments_for(keys)
    if not depts:
        return {"symptom_keys": keys, "departments": [], "hint": ""}

    if len(depts) == 1:
        hint = f"이런 증상은 일반적으로 {depts[0]}에서 진료합니다."
    else:
        hint = (
            f"이런 증상은 일반적으로 {', '.join(depts[:2])} 등에서 진료합니다. "
            f"어느 과인지 판단이 어려우면 가정의학과에서 1차 상담을 받을 수 있습니다."
        )
    hint += " (증상에 따라 다른 과로 연계될 수 있으며, 응급 신호가 있으면 진료과 선택보다 119·응급실 이용이 우선입니다.)"
    return {"symptom_keys": keys, "departments": depts, "hint": hint}


def reload_matcher() -> int:
    """인덱스 강제 재구축 (테스트·갱신용). term 수 반환."""
    global _INDEX, _TERM_LIST, _BUILT
    _INDEX = {}
    _TERM_LIST = []
    _BUILT = False
    _build_index()
    return len(_INDEX)
