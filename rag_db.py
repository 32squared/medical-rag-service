"""
rag_db.py — RAG 전용 DB 함수
==============================
dbcommon 의 공유 연결 레이어(get_conn, _p, _ph, _row_to_dict, _now)를
import 해서 사용한다. (4-E 수렴: db facade → dbcommon 직접 import)
dbcommon 은 이 모듈을 import 하지 않는다(순환 임포트 방지).
호출처(rag_engine.py, review_queue.py 등)는 직접 이 모듈을 import 하라.

향후 RAG 스키마 변경은 ensure_rag_schema() 에 idempotent ALTER/CREATE 로
추가한다. 기존 db.py 의 kb_*/rag_queries DDL 은 건드리지 마라.
"""

import json
import uuid as _uuid
from datetime import datetime, timezone

from dbcommon import get_conn, _p, _row_to_dict


# ════════════════════════════════════════
#  스키마 훅 (향후 RAG 전용 DDL 추가 위치)
# ════════════════════════════════════════

# 스키마 보장 1회 가드 (프로세스 단위)
_RAG_SCHEMA_ENSURED = False


def ensure_rag_schema():
    """
    RAG 전용 스키마 변경 훅 (멱등 실행 가능).
    향후 RAG 전용 테이블/컬럼 추가는 여기에 idempotent ALTER/CREATE 문으로 작성한다.
    ※ 기존 db.py 의 kb_sources / kb_documents / kb_chunks / rag_queries DDL 은
       이 함수로 이동하지 말 것 (리스크 — 별도 작업으로).

    rag_conversation_state: RAG 응급 상태머신(emergency_state)을 RAG 소유 테이블에 보관.
    (기존엔 호스트 conversations 테이블을 직접 SELECT/UPDATE 했다 → 런타임 결합 해제)
    PG/SQLite 공용 DDL.
    """
    with get_conn() as (conn, cur):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS rag_conversation_state (
                   conversation_id         TEXT PRIMARY KEY,
                   emergency_state         TEXT NOT NULL DEFAULT 'NORMAL',
                   emergency_redirected_at TEXT,
                   last_symptom_keys       TEXT DEFAULT '[]',
                   last_intent             TEXT,
                   last_departments        TEXT DEFAULT '[]',
                   turn_count              INTEGER DEFAULT 0,
                   context_updated_at      TEXT,
                   updated_at              TEXT NOT NULL
               )"""
        )
        # 기존(컬럼 없는) 테이블 대비 additive ALTER — 멱등(중복 컬럼 오류 무시).
        # 멀티턴 세션 컨텍스트 컬럼(06-multiturn-design.md §4). 원문 질의는 미저장(개인정보 최소화).
        for ddl in (
            "ALTER TABLE rag_conversation_state ADD COLUMN last_symptom_keys TEXT DEFAULT '[]'",
            "ALTER TABLE rag_conversation_state ADD COLUMN last_intent TEXT",
            "ALTER TABLE rag_conversation_state ADD COLUMN last_departments TEXT DEFAULT '[]'",
            "ALTER TABLE rag_conversation_state ADD COLUMN turn_count INTEGER DEFAULT 0",
            "ALTER TABLE rag_conversation_state ADD COLUMN context_updated_at TEXT",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass  # 이미 존재 → 무시(멱등)
        conn.commit()


def _ensure_once():
    """rag_conversation_state 스키마를 프로세스당 1회 보장(멱등, 비차단)."""
    global _RAG_SCHEMA_ENSURED
    if _RAG_SCHEMA_ENSURED:
        return
    try:
        ensure_rag_schema()
        _RAG_SCHEMA_ENSURED = True
    except Exception:
        pass  # 다음 호출에서 재시도


def get_conversation_state(conversation_id: str) -> dict:
    """RAG 소유 rag_conversation_state 에서 emergency_state 조회.
    행이 없으면 {"emergency_state": "NORMAL"}. (예외 처리/로깅은 호출자 rag_engine 담당)"""
    _ensure_once()
    with get_conn() as (conn, cur):
        cur.execute(
            f"SELECT emergency_state FROM rag_conversation_state "
            f"WHERE conversation_id = {_p()}",
            (conversation_id,),
        )
        row = cur.fetchone()
    if row:
        rd = _row_to_dict(row)
        return {"emergency_state": rd.get("emergency_state") or "NORMAL"}
    return {"emergency_state": "NORMAL"}


def set_conversation_state(conversation_id: str, state: str) -> None:
    """RAG 소유 rag_conversation_state UPSERT.
    state="EMERGENCY_REDIRECTED" 일 때만 emergency_redirected_at=now 기록.
    NORMAL 전환 시 기존 redirected_at 은 COALESCE 로 보존(기존 동작 보존)."""
    _ensure_once()
    now = datetime.now(timezone.utc).isoformat()
    redirected_at = now if state == "EMERGENCY_REDIRECTED" else None
    with get_conn() as (conn, cur):
        cur.execute(
            f"INSERT INTO rag_conversation_state "
            f"(conversation_id, emergency_state, emergency_redirected_at, updated_at) "
            f"VALUES ({_p()},{_p()},{_p()},{_p()}) "
            f"ON CONFLICT (conversation_id) DO UPDATE SET "
            f"emergency_state = {_p()}, "
            f"emergency_redirected_at = COALESCE({_p()}, rag_conversation_state.emergency_redirected_at), "
            f"updated_at = {_p()}",
            (conversation_id, state, redirected_at, now,
             state, redirected_at, now),
        )
        conn.commit()


def _ctx_loads(val) -> list:
    """저장된 JSON 문자열 → 리스트(오류 시 빈 리스트)."""
    if not val:
        return []
    try:
        out = json.loads(val)
        return out if isinstance(out, list) else []
    except Exception:
        return []


def get_conversation_context(conversation_id: str) -> dict:
    """멀티턴 세션 컨텍스트 조회(06-multiturn-design.md §3).

    반환: {last_symptom_keys: [...], last_intent: str|None,
           last_departments: [...], turn_count: int}
    행 없음/오류 시 빈 컨텍스트(turn_count=0).
    """
    empty = {"last_symptom_keys": [], "last_intent": None,
             "last_departments": [], "turn_count": 0}
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT last_symptom_keys, last_intent, last_departments, turn_count "
                f"FROM rag_conversation_state WHERE conversation_id = {_p()}",
                (conversation_id,),
            )
            row = cur.fetchone()
    except Exception:
        return empty
    if not row:
        return empty
    rd = _row_to_dict(row)
    return {
        "last_symptom_keys": _ctx_loads(rd.get("last_symptom_keys")),
        "last_intent": rd.get("last_intent"),
        "last_departments": _ctx_loads(rd.get("last_departments")),
        "turn_count": int(rd.get("turn_count") or 0),
    }


def update_conversation_context(conversation_id: str, symptom_keys=None,
                                intent=None, departments=None) -> None:
    """이번 턴 결과로 세션 컨텍스트 갱신 + turn_count 증가(UPSERT).

    비식별 요약만 저장(증상키/intent/진료과). 원문 질의는 저장하지 않는다(§6-3).
    emergency_state 는 건드리지 않는다(별도 set_conversation_state 소관).
    """
    _ensure_once()
    now = datetime.now(timezone.utc).isoformat()
    sk = json.dumps(symptom_keys or [], ensure_ascii=False)
    dp = json.dumps(departments or [], ensure_ascii=False)
    with get_conn() as (conn, cur):
        cur.execute(
            f"INSERT INTO rag_conversation_state "
            f"(conversation_id, emergency_state, last_symptom_keys, last_intent, "
            f" last_departments, turn_count, context_updated_at, updated_at) "
            f"VALUES ({_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()}) "
            f"ON CONFLICT (conversation_id) DO UPDATE SET "
            f"last_symptom_keys = {_p()}, last_intent = {_p()}, "
            f"last_departments = {_p()}, "
            f"turn_count = rag_conversation_state.turn_count + 1, "
            f"context_updated_at = {_p()}, updated_at = {_p()}",
            (conversation_id, "NORMAL", sk, intent, dp, 1, now, now,
             sk, intent, dp, now, now),
        )
        conn.commit()


# ════════════════════════════════════════
#  Medical RAG 스펙 모듈 지원 (Review Queue / Audit)
# ════════════════════════════════════════

def add_review_item(data: dict):
    """고위험 답변 검수 큐(review_queue_items) 적재. 스키마 미적용/오류 시 None(비차단)."""
    try:
        item_id = "rvq-" + _uuid.uuid4().hex[:10]
        now = datetime.now(timezone.utc).isoformat()
        reasons = json.dumps(data.get("reasons", []), ensure_ascii=False)
        with get_conn() as (conn, cur):
            cur.execute(
                f"""INSERT INTO review_queue_items
                    (id, answer_id, rag_query_id, question, answer, priority,
                     assignee_role, reasons_json, status, created_at)
                    VALUES ({_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()})""",
                (item_id, data.get("answer_id"), data.get("rag_query_id"),
                 data.get("question"), data.get("answer"), data.get("priority", "medium"),
                 data.get("assignee_role", "doctor"), reasons,
                 data.get("status", "pending"), now),
            )
            conn.commit()
        return item_id
    except Exception:
        return None


def update_rag_query_audit(rag_query_id: str, **fields):
    """rag_queries 감사 필드(answer_id/model_version/prompt_version/classification_json/
    evidence_pack_json) 갱신. 스키마 미적용/오류 시 무시(비차단)."""
    if not rag_query_id or not fields:
        return False
    allowed = {"answer_id", "model_version", "prompt_version",
               "classification_json", "evidence_pack_json",
               "rewrite_method", "rewritten_from"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return False
    try:
        sets = ", ".join(f"{c} = {_p()}" for c in cols)
        params = [fields[c] for c in cols] + [rag_query_id]
        with get_conn() as (conn, cur):
            cur.execute(f"UPDATE rag_queries SET {sets} WHERE id = {_p()}", params)
            conn.commit()
        return True
    except Exception:
        return False


def record_response_feedback(rag_query_id: str, rating: str, *,
                             conversation_id: str = None, user_id: str = None,
                             reason_code: str = None):
    """답변 명시 피드백(👍/👎) 1건을 response_feedback에 적재하고,
    비식별 thumbs 이벤트를 analytics_events로 emit한다.

    코멘트 원문은 받지 않으며 rating·reason_code(코드)만 저장(비식별).
    성공 시 feedback id, 실패/유효성 위반 시 None.
    """
    if not rag_query_id or rating not in ("up", "down"):
        return None
    import uuid as _uuid
    from datetime import datetime, timezone
    fid = _uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO response_feedback "
                f"(id, rag_query_id, conversation_id, user_id, rating, reason_code, created_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (fid, rag_query_id, conversation_id, user_id, rating,
                 (reason_code or None), now),
            )
            conn.commit()
    except Exception:
        return None
    # 비식별 집계 이벤트 (비차단)
    try:
        import analytics_events as _ae
        _ae.emit(
            "thumbs_up" if rating == "up" else "thumbs_down",
            conversation_id=conversation_id, rag_query_id=rag_query_id,
        )
    except Exception:
        pass
    return fid


def list_review_queue(status: str = "pending", limit: int = 50) -> list:
    """검수 큐 조회 (스펙 §8.4 review console용). 오류 시 빈 리스트."""
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"""SELECT id, answer_id, question, priority, assignee_role,
                           reasons_json, status, created_at
                    FROM review_queue_items WHERE status = {_p()}
                    ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                             created_at DESC LIMIT {_p()}""",
                (status, limit),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


# ════════════════════════════════════════
#  웰니스 코칭 영속 (18 §7.2 · mig018) — 세션/플랜/체크인
#  값은 라벨·bool·JSON 항목 텍스트만. 원시 측정값/진단명은 미저장(코칭은 밴드 라벨만 받음).
# ════════════════════════════════════════
_COACHING_SCHEMA_ENSURED = False


def ensure_coaching_schema():
    """코칭 운영 테이블 멱등 보장 (PG/SQLite 공용). 정본 18 §7.2 / mig018."""
    with get_conn() as (conn, cur):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS coaching_session (
                   session_id       TEXT PRIMARY KEY,
                   conversation_id  TEXT,
                   mode             TEXT,
                   track            TEXT,
                   band_at_start    TEXT,
                   consent_personal INTEGER,
                   started_at       TEXT
               )""")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS coaching_plan (
                   plan_id             TEXT PRIMARY KEY,
                   session_id          TEXT,
                   track               TEXT,
                   items_json          TEXT,
                   target_period       TEXT,
                   band_at_creation    TEXT,
                   safety_banner       TEXT,
                   compliance_action   TEXT,
                   original_items_json TEXT,
                   created_at          TEXT
               )""")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS coaching_checkin (
                   checkin_id TEXT PRIMARY KEY,
                   plan_id    TEXT,
                   item_key   TEXT,
                   done       INTEGER,
                   ts         TEXT
               )""")
        conn.commit()
    # analytics_events 코칭 차원(mig019) 멱등 보강 — 러너 미적용 대비, 각 ALTER 독립 트랜잭션
    # (PG는 실패 statement가 트랜잭션을 오염시키므로 분리). 이미 있으면 무시.
    for ddl in (
        "ALTER TABLE analytics_events ADD COLUMN track TEXT",
        "ALTER TABLE analytics_events ADD COLUMN checkin_done INTEGER",
        "ALTER TABLE analytics_events ADD COLUMN streak INTEGER",
    ):
        try:
            with get_conn() as (conn, cur):
                cur.execute(ddl)
                conn.commit()
        except Exception:
            pass


def _ensure_coaching_once():
    global _COACHING_SCHEMA_ENSURED
    if _COACHING_SCHEMA_ENSURED:
        return
    try:
        ensure_coaching_schema()
        _COACHING_SCHEMA_ENSURED = True
    except Exception:
        pass  # 다음 호출에서 재시도


def create_coaching_session(*, conversation_id=None, mode="medical", track=None,
                            band_at_start=None, consent_personal=False):
    """코칭 세션 1건 생성 → session_id. 비식별 track_selected 이벤트 emit. 실패 시 None."""
    _ensure_coaching_once()
    sid = _uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO coaching_session (session_id, conversation_id, mode, track, "
                f"band_at_start, consent_personal, started_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (sid, conversation_id, mode, track, band_at_start,
                 1 if consent_personal else 0, now),
            )
            conn.commit()
    except Exception:
        return None
    try:
        import analytics_events as _ae
        _ae.emit("coaching_track_selected", conversation_id=conversation_id,
                 track=track, risk_level=band_at_start)
    except Exception:
        pass
    return sid


def save_coaching_plan(*, session_id, track=None, items=None, target_period=None,
                       band=None, safety_banner=None, compliance_action="pass",
                       original_items=None, conversation_id=None):
    """코칭 플랜 1건 저장(items=항목 리스트 → JSON) → plan_id. plan_shown 이벤트 emit."""
    _ensure_coaching_once()
    pid = _uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO coaching_plan (plan_id, session_id, track, items_json, "
                f"target_period, band_at_creation, safety_banner, compliance_action, "
                f"original_items_json, created_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (pid, session_id, track, json.dumps(items or [], ensure_ascii=False),
                 target_period, band, safety_banner, compliance_action,
                 json.dumps(original_items, ensure_ascii=False) if original_items is not None else None,
                 now),
            )
            conn.commit()
    except Exception:
        return None
    try:
        import analytics_events as _ae
        _ae.emit("coaching_plan_shown", conversation_id=conversation_id,
                 track=track, risk_level=band)
    except Exception:
        pass
    return pid


def record_coaching_checkin(*, plan_id, item_key=None, done=True, conversation_id=None):
    """일일 체크인 1건 기록 → checkin_id. coaching_checkin 이벤트(done bool) emit."""
    _ensure_coaching_once()
    cid = _uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO coaching_checkin (checkin_id, plan_id, item_key, done, ts) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (cid, plan_id, item_key, 1 if done else 0, now),
            )
            conn.commit()
    except Exception:
        return None
    try:
        import analytics_events as _ae
        _ae.emit("coaching_checkin", conversation_id=conversation_id, checkin_done=done)
    except Exception:
        pass
    return cid


def get_coaching_checkins(plan_id) -> list:
    """플랜의 체크인 목록(시간순) → [{item_key, done, ts}]. 오류 시 빈 리스트."""
    _ensure_coaching_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT item_key, done, ts FROM coaching_checkin "
                f"WHERE plan_id = {_p()} ORDER BY ts",
                (plan_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def get_latest_coaching_plan(conversation_id) -> dict:
    """주체(conversation_id=subject_id)의 가장 최근 코칭 플랜 → dict(items_json 포함) 또는 None.
    BFF 가 conversation_id 에 계정 id 를 넣어 **개인별 영속**(재로그인 복원)에 사용."""
    _ensure_coaching_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT p.plan_id, p.track, p.items_json, p.target_period, "
                f"p.band_at_creation, p.safety_banner, p.created_at "
                f"FROM coaching_plan p JOIN coaching_session s ON p.session_id = s.session_id "
                f"WHERE s.conversation_id = {_p()} ORDER BY p.created_at DESC LIMIT 1",
                (conversation_id,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


# ════════════════════════════════════════
#  채팅 히스토리 영속 — 재로그인 시 대화 복원 (conversation_id=subject_id, 개인별).
#  저장: 사용자 질문 텍스트 + AI 답변 텍스트·출처(JSON)·맞춤안내 여부. 원시 측정값/진단명 없음.
# ════════════════════════════════════════
_CHAT_SCHEMA_ENSURED = False


def ensure_chat_schema():
    """채팅 메시지 테이블 멱등 보장 (PG/SQLite 공용)."""
    with get_conn() as (conn, cur):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS chat_message (
                   message_id      TEXT PRIMARY KEY,
                   conversation_id TEXT,
                   role            TEXT,
                   text            TEXT,
                   citations_json  TEXT,
                   personalize     INTEGER,
                   created_at      TEXT
               )""")
        conn.commit()


def _ensure_chat_once():
    global _CHAT_SCHEMA_ENSURED
    if _CHAT_SCHEMA_ENSURED:
        return
    try:
        ensure_chat_schema()
        _CHAT_SCHEMA_ENSURED = True
    except Exception:
        pass


def save_chat_message(*, conversation_id, role, text, citations=None, personalize=None):
    """채팅 메시지 1건 저장 → message_id. role='user'|'ai'. 실패 시 None(대화는 계속)."""
    _ensure_chat_once()
    mid = _uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO chat_message (message_id, conversation_id, role, text, "
                f"citations_json, personalize, created_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (mid, conversation_id, role, text,
                 json.dumps(citations, ensure_ascii=False) if citations is not None else None,
                 (1 if personalize else 0) if personalize is not None else None,
                 now),
            )
            conn.commit()
    except Exception:
        return None
    return mid


def get_chat_history(conversation_id, limit=50) -> list:
    """주체(conversation_id=subject_id)의 최근 메시지 → 시간순 리스트. 오류 시 빈 리스트."""
    _ensure_chat_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT role, text, citations_json, personalize, created_at FROM chat_message "
                f"WHERE conversation_id = {_p()} ORDER BY created_at DESC LIMIT {int(limit)}",
                (conversation_id,),
            )
            rows = [_row_to_dict(r) for r in cur.fetchall()]
            return list(reversed(rows))     # 최근 N건을 시간순으로
    except Exception:
        return []
