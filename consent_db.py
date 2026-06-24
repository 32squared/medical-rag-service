"""
동의원장(consent ledger) 데이터 계층 — P0 런치블로커 B 핵심.

append-only 원장: 레코드를 UPDATE/DELETE 하지 않는다. 철회 = action='revoke'
신규 레코드. 현재 유효 상태 = 주체×항목 최신 레코드의 action=='grant'. 전체 이력·
감사·개인정보보호법 철회권 충족.

정본: docs/plan/23-p0-detailed-design.md §2·§4 / migration 020.
순수 판정(resolve_current·personalization_allowed·missing_required)은 DB 없이
테스트 가능. DB 함수는 dbcommon 경유(PG/SQLite 듀얼). 실패는 None/[] 로 degrade.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dbcommon import get_conn, _p

GRANT = "grant"
REVOKE = "revoke"

# P0 동의 항목 정의(정본 23 §2). version 1 = 초판.
CONSENT_ITEMS = {
    "personal_info":  {"required": True,  "title": "개인정보 수집·이용"},
    "sensitive_info": {"required": False, "title": "민감정보(건강·검진) 처리"},
    "cross_border":   {"required": False, "title": "개인정보 국외이전"},
    "location":       {"required": False, "title": "위치정보 이용"},
    "push":           {"required": False, "title": "광고성 정보 수신(푸시)"},
    "phr_link":       {"required": False, "title": "공단 건강검진 연동"},
}

_SCHEMA_ENSURED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── 스키마 멱등 보장 ─────────────────────────────────────────
def ensure_consent_schema() -> None:
    """동의원장 테이블 멱등 보장 (PG/SQLite 공용). 정본 23 §2 / mig020."""
    with get_conn() as (conn, cur):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS consent_item (
                   item_key     TEXT    NOT NULL,
                   version      INTEGER NOT NULL,
                   title        TEXT,
                   body_url     TEXT,
                   required     INTEGER,
                   effective_at TEXT,
                   PRIMARY KEY (item_key, version)
               )""")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS consent_record (
                   id            TEXT PRIMARY KEY,
                   subject_id    TEXT NOT NULL,
                   item_key      TEXT NOT NULL,
                   item_version  INTEGER,
                   action        TEXT NOT NULL,
                   source        TEXT,
                   created_at    TEXT NOT NULL,
                   evidence_hash TEXT
               )""")
        cur.execute(
            """CREATE INDEX IF NOT EXISTS idx_consent_record_subject
                   ON consent_record(subject_id, item_key, created_at)""")
        conn.commit()
    # analytics_events 동의 차원(mig022) 멱등 보강 — 러너 미적용 대비, 독립 트랜잭션
    # (PG는 실패 statement가 트랜잭션을 오염시키므로 분리). 이미 있으면 무시.
    try:
        with get_conn() as (conn, cur):
            cur.execute("ALTER TABLE analytics_events ADD COLUMN consent_item TEXT")
            conn.commit()
    except Exception:
        pass


def _ensure_once() -> None:
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    try:
        ensure_consent_schema()
        _SCHEMA_ENSURED = True
    except Exception:
        pass  # 다음 호출에서 재시도


# ── 순수 판정 (DB 불필요, 테스트 가능) ───────────────────────
def resolve_current(records: List[Dict]) -> Dict[str, Dict]:
    """레코드 목록 → item_key별 최신 레코드. created_at 최대 기준.
    동시각 동률(같은 created_at)은 **안전측(revoke) 우선** — DB 행순서에 의존하지
    않고 '철회 즉시 반영' 불변을 보장(PG의 tie 재정렬에도 grant 가 revoke 를 덮지 않음)."""
    latest: Dict[str, Dict] = {}
    for r in records:
        k = r["item_key"]
        cur = latest.get(k)
        if cur is None or r["created_at"] > cur["created_at"]:
            latest[k] = r
        elif r["created_at"] == cur["created_at"] and r.get("action") == REVOKE:
            latest[k] = r
    return latest


def granted_items(records: List[Dict]) -> set:
    """현재 grant 상태인 item_key 집합."""
    return {k for k, r in resolve_current(records).items() if r["action"] == GRANT}


def personalization_allowed(records: List[Dict], *, cross_border_needed: bool = False) -> bool:
    """개인화(민감 라벨·방향2) 허용 여부 — 23 §4 게이트의 ledger 판정.
    personal_info AND sensitive_info, 국외 LLM 경로면 cross_border 까지 필요."""
    g = granted_items(records)
    if "personal_info" not in g or "sensitive_info" not in g:
        return False
    if cross_border_needed and "cross_border" not in g:
        return False
    return True


def missing_required(records: List[Dict]) -> List[str]:
    """필수 동의 중 미취득 항목 — 가입/이용 차단 게이트."""
    g = granted_items(records)
    return [k for k, v in CONSENT_ITEMS.items() if v["required"] and k not in g]


# ── DB 영속 ──────────────────────────────────────────────────
def record_consent(subject_id, item_key, action, *, item_version=1,
                   source="onboarding", evidence_hash=None) -> Optional[str]:
    """동의 레코드 1건 append (grant/revoke). 실패 시 None."""
    _ensure_once()
    rid = _uuid.uuid4().hex
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO consent_record (id, subject_id, item_key, item_version, "
                f"action, source, created_at, evidence_hash) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (rid, subject_id, item_key, item_version, action, source, _now_iso(), evidence_hash),
            )
            conn.commit()
    except Exception:
        return None
    return rid


def grant(subject_id, item_key, **kw) -> Optional[str]:
    return record_consent(subject_id, item_key, GRANT, **kw)


def revoke(subject_id, item_key, **kw) -> Optional[str]:
    return record_consent(subject_id, item_key, REVOKE, **kw)


def get_records(subject_id, item_key=None) -> List[Dict]:
    """주체(선택적으로 항목)의 동의 레코드 — created_at 오름차순."""
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            if item_key:
                cur.execute(
                    f"SELECT * FROM consent_record WHERE subject_id={_p()} AND item_key={_p()} "
                    f"ORDER BY created_at", (subject_id, item_key))
            else:
                cur.execute(
                    f"SELECT * FROM consent_record WHERE subject_id={_p()} ORDER BY created_at",
                    (subject_id,))
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def current_state(subject_id) -> Dict[str, Dict]:
    """주체의 항목별 현재 유효 레코드."""
    return resolve_current(get_records(subject_id))


def is_granted(subject_id, item_key) -> bool:
    """주체×항목 현재 grant 여부."""
    return item_key in granted_items(get_records(subject_id))


def history(subject_id, item_key=None) -> List[Dict]:
    """동의 이력(감사) — created_at 오름차순."""
    return get_records(subject_id, item_key=item_key)
