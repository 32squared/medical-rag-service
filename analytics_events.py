"""
analytics_events.py — 비식별 이벤트 스토어 기록 (개선 루프 E2).

대화 1턴마다 '무슨 일이 얼마나'를 라벨·카운트·불리언으로만 analytics_events에 적재한다.
질의 원문·원시 측정값·진단명·PII는 구조적으로 미저장 — 화이트리스트 컬럼만 INSERT하고,
그 외 키는 sanitize()에서 폐기한다(비식별 보장의 핵심).

  - BI(Metabase/Grafana)는 이 테이블만 조회. rag_queries(원문 보유)는 미조회.
  - fail-closed·비차단: 기록 실패는 응답 생성을 막지 않는다(로깅 후 None 반환).

정본: docs/ontology/feedback-ontology.ttl
  phr:EventStore / phr:AnalyticsEvent / phr:deidProps (E2)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── 화이트리스트 — 이 차원만 저장 가능. deidProps(E2)와 일치 ──────────────
_LABEL_FIELDS = (
    "intent", "primary_domain", "risk_level",
    "guardrail_action", "gate_decision", "evidence_quality",
)
_COUNT_FIELDS = ("citations_count", "latency_ms")
_BOOL_FIELDS = (
    "is_followup", "had_personal_block", "gave_referral", "refusal", "emergency",
)
ALLOWED_PROPS = frozenset(_LABEL_FIELDS + _COUNT_FIELDS + _BOOL_FIELDS)

# 등록된 이벤트만 적재 (오타·임의 이벤트 차단)
EVENT_NAMES = frozenset({
    "query_received",        # 진입 — 분류 직후(퍼널 분모·intent 분포)
    "answer_shown",          # 정상 답변 노출
    "insufficient_evidence", # 근거부족 → 길안내 전환(거절수요 신호)
    "emergency_redirect",    # 응급 안내
    "triage_clarify",        # 비의료/모호 입력 되묻기
    "thumbs_up",             # 명시 피드백 👍
    "thumbs_down",           # 명시 피드백 👎
})

_MAX_LABEL_LEN = 64


def _coerce_label(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:_MAX_LABEL_LEN] if s else None


def _coerce_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_bool(v) -> Optional[int]:
    if v is None:
        return None
    return 1 if v else 0


def sanitize(props: dict) -> dict:
    """화이트리스트 외 키 폐기 + 타입 강제. 호출자가 실수로 원문/수치를 넘겨도
    컬럼이 없으면 저장되지 않는다(구조적 비식별)."""
    out: dict = {}
    for k in _LABEL_FIELDS:
        if k in props:
            out[k] = _coerce_label(props[k])
    for k in _COUNT_FIELDS:
        if k in props:
            out[k] = _coerce_int(props[k])
    for k in _BOOL_FIELDS:
        if k in props:
            out[k] = _coerce_bool(props[k])
    return out


def emit(event_name: str, *, conversation_id: str = None,
         rag_query_id: str = None, **props) -> Optional[str]:
    """비식별 이벤트 1건을 analytics_events에 적재. 실패 시 None(비차단).

    props는 ALLOWED_PROPS 화이트리스트만 통과한다. 그 외 키는 무시된다.
    """
    if event_name not in EVENT_NAMES:
        logger.debug("[Analytics] 미등록 event_name=%s — 스킵", event_name)
        return None

    clean = sanitize(props)
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cols = ["id", "event_name", "conversation_id", "rag_query_id"]
    vals = [event_id, event_name, conversation_id, rag_query_id]
    for k, v in clean.items():
        cols.append(k)
        vals.append(v)
    cols.append("created_at")
    vals.append(now)

    try:
        from dbcommon import get_conn, _p
        placeholders = ", ".join(_p() for _ in cols)
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO analytics_events ({', '.join(cols)}) "
                f"VALUES ({placeholders})",
                vals,
            )
            conn.commit()
        return event_id
    except Exception as e:
        logger.debug("[Analytics] INSERT 스킵: %s", e)
        return None
