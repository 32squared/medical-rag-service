"""
Conversation Context — 멀티턴 세션 컨텍스트 (06-multiturn-design.md §3, §7-2).

대화 단위로 직전 턴의 *비식별 요약*(증상키·intent·진료과·turn_count)을 보관해,
후속질의 재작성(followup_rewriter)에 직전 주제를 공급한다.

- 저장은 rag_db.rag_conversation_state 에 위임(emergency_state와 같은 테이블의 추가 컬럼).
- 원문 질의는 저장하지 않는다(개인정보 최소화, §6-3).
- 로드/갱신 실패는 비차단(빈 컨텍스트로 graceful degrade) — 멀티턴이 단일턴 동작을 깨지 않게.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_EMPTY: Dict = {
    "last_symptom_keys": [],
    "last_intent": None,
    "last_departments": [],
    "turn_count": 0,
}


def load_context(conversation_id: str) -> Dict:
    """세션 컨텍스트 로드(rag_db 위임). 오류/미존재 시 빈 컨텍스트."""
    if not conversation_id:
        return dict(_EMPTY)
    try:
        import rag_db
        return rag_db.get_conversation_context(conversation_id)
    except Exception as e:
        logger.debug("[ConvCtx] load 실패(빈 컨텍스트로 진행): %s", e)
        return dict(_EMPTY)


def update_context(
    conversation_id: str,
    symptom_keys: Optional[List[str]] = None,
    intent: Optional[str] = None,
    departments: Optional[List[str]] = None,
) -> None:
    """이번 턴 결과로 세션 컨텍스트 갱신(rag_db 위임, turn_count 증가). 오류 비차단."""
    if not conversation_id:
        return
    try:
        import rag_db
        rag_db.update_conversation_context(
            conversation_id,
            symptom_keys=symptom_keys,
            intent=intent,
            departments=departments,
        )
    except Exception as e:
        logger.debug("[ConvCtx] update 실패(무시): %s", e)


def name_for_key(symptom_key: str) -> str:
    """증상키 → 대표 한글명(후속질의 재작성용). 없으면 빈 문자열."""
    if not symptom_key:
        return ""
    try:
        from symptom_catalog import load_catalog
        item = load_catalog().get(symptom_key) or {}
        return item.get("symptom_name") or ""
    except Exception:
        return ""


def last_symptom_name(context: Dict) -> str:
    """컨텍스트의 첫 last_symptom_key → 대표 한글명(재작성 주어). 없으면 ''."""
    keys = (context or {}).get("last_symptom_keys") or []
    return name_for_key(keys[0]) if keys else ""
