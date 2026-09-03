"""metrics_repo.py — 오늘의 나 재미 레이어 영속 계층(일일 지표·아키타입·공유 카드·웰니스 타입·월간 희귀도).

정본: docs/design/todays-me-mockups/02-dev-requirements.md §3.

설계(routine_repo 관례 그대로):
  - 스키마는 migrations/024 + in-code 멱등 ensure.
  - 격리 키 = subject_id. 기존 routine_* 테이블은 읽지도 쓰지도 않는다(두 기준선 분리, C6).
  - 저장 금지: 검진 수치·밴드 라벨(band_snapshot 은 컬렉션 제외 판정용 라벨 1개만).
  - 모든 함수는 예외를 밖으로 던지지 않는다(조회=빈값, 쓰기=None/False).
"""
from __future__ import annotations

import json
import uuid as _uuid
from typing import Dict, List, Optional, Sequence

from dbcommon import get_conn, _p, _row_to_dict
from routine_repo import now_iso, today_kst, add_days  # noqa: F401  (시간 유틸 재사용)

_SCHEMA_ENSURED = False

_DDL = [
    """CREATE TABLE IF NOT EXISTS daily_metrics (
           subject_id TEXT NOT NULL, metric_date TEXT NOT NULL,
           water_cups INTEGER DEFAULT 0, steps INTEGER, steps_source TEXT DEFAULT 'none',
           steps_synced_at TEXT, steps_confirmed INTEGER DEFAULT 0,
           mind_seconds INTEGER DEFAULT 0, mind_sessions INTEGER DEFAULT 0,
           bedtime_at TEXT, band_snapshot TEXT, created_at TEXT, updated_at TEXT,
           PRIMARY KEY (subject_id, metric_date))""",
    "CREATE INDEX IF NOT EXISTS ix_daily_metrics_subject ON daily_metrics (subject_id, metric_date)",
    """CREATE TABLE IF NOT EXISTS archetype_result (
           subject_id TEXT NOT NULL, metric_date TEXT NOT NULL, archetype_id TEXT NOT NULL,
           completed_tracks TEXT NOT NULL, rarity_pct INTEGER, reveal_seen_at TEXT,
           created_at TEXT, updated_at TEXT, PRIMARY KEY (subject_id, metric_date))""",
    """CREATE TABLE IF NOT EXISTS share_card (
           card_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, metric_date TEXT NOT NULL,
           archetype_id TEXT NOT NULL, theme_id TEXT DEFAULT 'coral', stickers_json TEXT DEFAULT '[]',
           comment TEXT, hide_numbers INTEGER DEFAULT 0, metrics_snapshot TEXT NOT NULL,
           rarity_pct INTEGER, locked_at TEXT, created_at TEXT, updated_at TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_share_card_day ON share_card (subject_id, metric_date)",
    """CREATE TABLE IF NOT EXISTS wellness_type (
           subject_id TEXT PRIMARY KEY, type_id TEXT NOT NULL, assigned_by TEXT NOT NULL,
           quiz_answers TEXT, assigned_at TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS archetype_monthly_stat (
           month TEXT NOT NULL, archetype_id TEXT NOT NULL, user_count INTEGER NOT NULL,
           denominator INTEGER NOT NULL, computed_at TEXT, PRIMARY KEY (month, archetype_id))""",
]


def ensure_schema() -> None:
    for ddl in _DDL:
        try:
            with get_conn() as (conn, cur):
                cur.execute(ddl)
                conn.commit()
        except Exception:
            pass


def _ensure() -> None:
    global _SCHEMA_ENSURED
    if not _SCHEMA_ENSURED:
        ensure_schema()
        _SCHEMA_ENSURED = True


def _one(sql: str, params: tuple) -> Optional[Dict]:
    try:
        with get_conn() as (conn, cur):
            cur.execute(sql, params)
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


def _all(sql: str, params: tuple) -> List[Dict]:
    try:
        with get_conn() as (conn, cur):
            cur.execute(sql, params)
            return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def _exec(sql: str, params: tuple) -> bool:
    try:
        with get_conn() as (conn, cur):
            cur.execute(sql, params)
            conn.commit()
        return True
    except Exception:
        return False


# ══════════════════════════ daily_metrics ══════════════════════════
_METRIC_FIELDS = ("water_cups", "steps", "steps_source", "steps_synced_at", "steps_confirmed",
                  "mind_seconds", "mind_sessions", "bedtime_at", "band_snapshot")


def get_day(subject_id: str, metric_date: str) -> Optional[Dict]:
    _ensure()
    return _one(f"SELECT * FROM daily_metrics WHERE subject_id = {_p()} AND metric_date = {_p()}",
                (subject_id, metric_date))


def upsert_day(subject_id: str, metric_date: str, **fields) -> Optional[Dict]:
    """부분 갱신 upsert. 넘긴 필드만 바꾼다. 반환: 갱신된 행."""
    _ensure()
    fields = {k: v for k, v in fields.items() if k in _METRIC_FIELDS}
    now = now_iso()
    existing = get_day(subject_id, metric_date)
    if existing:
        if fields:
            sets = ", ".join(f"{k} = {_p()}" for k in fields) + f", updated_at = {_p()}"
            ok = _exec(f"UPDATE daily_metrics SET {sets} WHERE subject_id = {_p()} AND metric_date = {_p()}",
                       tuple(fields.values()) + (now, subject_id, metric_date))
            if not ok:
                return None
        return get_day(subject_id, metric_date)
    cols = ["subject_id", "metric_date"] + list(fields) + ["created_at", "updated_at"]
    vals = [subject_id, metric_date] + list(fields.values()) + [now, now]
    ok = _exec(f"INSERT INTO daily_metrics ({', '.join(cols)}) VALUES ({', '.join([_p()] * len(cols))})",
               tuple(vals))
    if not ok:                          # PK 경합 → 재시도 1회(UPDATE 경로)
        return upsert_day(subject_id, metric_date, **fields) if get_day(subject_id, metric_date) else None
    return get_day(subject_id, metric_date)


def add_mind_session(subject_id: str, metric_date: str, seconds: int = 60) -> Optional[Dict]:
    cur = get_day(subject_id, metric_date) or {}
    return upsert_day(subject_id, metric_date,
                      mind_seconds=int(cur.get("mind_seconds") or 0) + max(0, int(seconds)),
                      mind_sessions=int(cur.get("mind_sessions") or 0) + 1)


def last_days(subject_id: str, end_date: str, n: int = 7) -> List[Dict]:
    """end_date 포함 최근 n일(있는 행만, 날짜 오름차순)."""
    _ensure()
    start = add_days(end_date, -(max(1, n) - 1))
    return _all(f"SELECT * FROM daily_metrics WHERE subject_id = {_p()} AND metric_date >= {_p()} "
                f"AND metric_date <= {_p()} ORDER BY metric_date ASC", (subject_id, start, end_date))


# ══════════════════════════ archetype_result ══════════════════════════
def get_archetype(subject_id: str, metric_date: str) -> Optional[Dict]:
    _ensure()
    row = _one(f"SELECT * FROM archetype_result WHERE subject_id = {_p()} AND metric_date = {_p()}",
               (subject_id, metric_date))
    if row:
        try:
            row["completed_tracks"] = json.loads(row.get("completed_tracks") or "[]")
        except Exception:
            row["completed_tracks"] = []
    return row


def set_archetype(subject_id: str, metric_date: str, archetype_id: Optional[str],
                  tracks: Sequence[str], rarity: Optional[int] = None) -> Optional[Dict]:
    """조합 재계산 결과 반영. archetype_id 가 None(0완료)이면 행을 지운다."""
    _ensure()
    now = now_iso()
    if not archetype_id:
        _exec(f"DELETE FROM archetype_result WHERE subject_id = {_p()} AND metric_date = {_p()}",
              (subject_id, metric_date))
        return None
    tj = json.dumps(list(tracks), ensure_ascii=False)
    existing = get_archetype(subject_id, metric_date)
    if existing:
        _exec(f"UPDATE archetype_result SET archetype_id = {_p()}, completed_tracks = {_p()}, "
              f"rarity_pct = {_p()}, updated_at = {_p()} WHERE subject_id = {_p()} AND metric_date = {_p()}",
              (archetype_id, tj, rarity, now, subject_id, metric_date))
    else:
        _exec(f"INSERT INTO archetype_result (subject_id, metric_date, archetype_id, completed_tracks, "
              f"rarity_pct, reveal_seen_at, created_at, updated_at) VALUES ({', '.join([_p()] * 8)})",
              (subject_id, metric_date, archetype_id, tj, rarity, None, now, now))
    return get_archetype(subject_id, metric_date)


def mark_seen(subject_id: str, metric_date: str) -> Optional[str]:
    now = now_iso()
    ok = _exec(f"UPDATE archetype_result SET reveal_seen_at = COALESCE(reveal_seen_at, {_p()}), updated_at = {_p()} "
               f"WHERE subject_id = {_p()} AND metric_date = {_p()}", (now, now, subject_id, metric_date))
    row = get_archetype(subject_id, metric_date) if ok else None
    return (row or {}).get("reveal_seen_at")


def collection(subject_id: str, end_date: str, n: int = 7) -> List[Dict]:
    """아키타입을 받은 날만(빈 슬롯 없음). 경고 밴드였던 날 제외(spec-03 §5-4)."""
    _ensure()
    start = add_days(end_date, -(max(1, n) - 1))
    rows = _all(f"SELECT a.metric_date, a.archetype_id, d.band_snapshot FROM archetype_result a "
                f"LEFT JOIN daily_metrics d ON d.subject_id = a.subject_id AND d.metric_date = a.metric_date "
                f"WHERE a.subject_id = {_p()} AND a.metric_date >= {_p()} AND a.metric_date <= {_p()} "
                f"ORDER BY a.metric_date ASC", (subject_id, start, end_date))
    return [{"date": r["metric_date"], "archetype_id": r["archetype_id"],
             "is_today": r["metric_date"] == end_date}
            for r in rows if (r.get("band_snapshot") or "") not in ("경고", "응급")]


# ══════════════════════════ archetype_monthly_stat ══════════════════════════
def monthly_stat(month: str, archetype_id: str) -> Optional[Dict]:
    _ensure()
    return _one(f"SELECT * FROM archetype_monthly_stat WHERE month = {_p()} AND archetype_id = {_p()}",
                (month, archetype_id))


def recompute_monthly_stats(month: str) -> Dict[str, Dict]:
    """월간 사용자 단위 분포(spec-03 §5-3). 배치·테스트에서 호출."""
    _ensure()
    rows = _all(f"SELECT subject_id, archetype_id, metric_date FROM archetype_result WHERE metric_date LIKE {_p()}",
                (month + "-%",))
    users = {r["subject_id"] for r in rows}
    per: Dict[str, set] = {}
    for r in rows:
        per.setdefault(r["archetype_id"], set()).add(r["subject_id"])
    now = now_iso()
    out = {}
    for aid, s in per.items():
        _exec(f"DELETE FROM archetype_monthly_stat WHERE month = {_p()} AND archetype_id = {_p()}", (month, aid))
        _exec(f"INSERT INTO archetype_monthly_stat (month, archetype_id, user_count, denominator, computed_at) "
              f"VALUES ({', '.join([_p()] * 5)})", (month, aid, len(s), len(users), now))
        out[aid] = {"user_count": len(s), "denominator": len(users)}
    return out


# ══════════════════════════ wellness_type ══════════════════════════
def get_wellness_type(subject_id: str) -> Optional[Dict]:
    _ensure()
    return _one(f"SELECT * FROM wellness_type WHERE subject_id = {_p()}", (subject_id,))


def set_wellness_type(subject_id: str, type_id: str, assigned_by: str,
                      answers: Optional[Sequence[int]] = None) -> Optional[Dict]:
    _ensure()
    now = now_iso()
    aj = json.dumps(list(answers)) if answers is not None else None
    if get_wellness_type(subject_id):
        _exec(f"UPDATE wellness_type SET type_id = {_p()}, assigned_by = {_p()}, quiz_answers = COALESCE({_p()}, quiz_answers), "
              f"assigned_at = {_p()}, updated_at = {_p()} WHERE subject_id = {_p()}",
              (type_id, assigned_by, aj, now, now, subject_id))
    else:
        _exec(f"INSERT INTO wellness_type (subject_id, type_id, assigned_by, quiz_answers, assigned_at, updated_at) "
              f"VALUES ({', '.join([_p()] * 6)})", (subject_id, type_id, assigned_by, aj, now, now))
    return get_wellness_type(subject_id)


# ══════════════════════════ share_card ══════════════════════════
def get_card(card_id: str) -> Optional[Dict]:
    _ensure()
    row = _one(f"SELECT * FROM share_card WHERE card_id = {_p()}", (card_id,))
    return _decode_card(row)


def get_card_by_day(subject_id: str, metric_date: str) -> Optional[Dict]:
    _ensure()
    row = _one(f"SELECT * FROM share_card WHERE subject_id = {_p()} AND metric_date = {_p()}",
               (subject_id, metric_date))
    return _decode_card(row)


def _decode_card(row: Optional[Dict]) -> Optional[Dict]:
    if not row:
        return None
    for k, default in (("stickers_json", "[]"), ("metrics_snapshot", "{}")):
        try:
            row[k] = json.loads(row.get(k) or default)
        except Exception:
            row[k] = json.loads(default)
    row["hide_numbers"] = bool(int(row.get("hide_numbers") or 0))
    return row


def create_card(subject_id: str, metric_date: str, archetype_id: str, theme_id: str,
                metrics_snapshot: Dict, rarity: Optional[int], locked_at: str) -> Optional[Dict]:
    _ensure()
    existing = get_card_by_day(subject_id, metric_date)
    if existing:
        return existing
    cid = _uuid.uuid4().hex
    now = now_iso()
    _exec(f"INSERT INTO share_card (card_id, subject_id, metric_date, archetype_id, theme_id, stickers_json, "
          f"comment, hide_numbers, metrics_snapshot, rarity_pct, locked_at, created_at, updated_at) "
          f"VALUES ({', '.join([_p()] * 13)})",
          (cid, subject_id, metric_date, archetype_id, theme_id, "[]", None, 0,
           json.dumps(metrics_snapshot, ensure_ascii=False), rarity, locked_at, now, now))
    return get_card_by_day(subject_id, metric_date)


def update_card(card_id: str, *, theme_id: Optional[str] = None, stickers: Optional[Sequence[Dict]] = None,
                comment: Optional[str] = None, hide_numbers: Optional[bool] = None,
                clear_comment: bool = False) -> Optional[Dict]:
    _ensure()
    sets, vals = [], []
    if theme_id is not None:
        sets.append(f"theme_id = {_p()}"); vals.append(theme_id)
    if stickers is not None:
        sets.append(f"stickers_json = {_p()}"); vals.append(json.dumps(list(stickers), ensure_ascii=False))
    if clear_comment:
        sets.append(f"comment = {_p()}"); vals.append(None)
    elif comment is not None:
        sets.append(f"comment = {_p()}"); vals.append(comment)
    if hide_numbers is not None:
        sets.append(f"hide_numbers = {_p()}"); vals.append(1 if hide_numbers else 0)
    if sets:
        sets.append(f"updated_at = {_p()}"); vals.append(now_iso())
        _exec(f"UPDATE share_card SET {', '.join(sets)} WHERE card_id = {_p()}", tuple(vals) + (card_id,))
    return get_card(card_id)


def list_cards(subject_id: str, month: Optional[str] = None) -> List[Dict]:
    _ensure()
    if month:
        rows = _all(f"SELECT card_id, metric_date, archetype_id, theme_id FROM share_card WHERE subject_id = {_p()} "
                    f"AND metric_date LIKE {_p()} ORDER BY metric_date DESC", (subject_id, month + "-%"))
    else:
        rows = _all(f"SELECT card_id, metric_date, archetype_id, theme_id FROM share_card WHERE subject_id = {_p()} "
                    f"ORDER BY metric_date DESC", (subject_id,))
    return rows
