"""
kb_collect.ledger — 수집 실행 기록(kb_collect_runs) 과 due 판정.

테이블은 migrations/026_kb_collect_runs*.sql. PG·SQLite 공용(dbcommon).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from dbcommon import _p, get_conn


def record_run(source_id: str, *, started_at: str, finished_at: str, status: str,
               fetched: int = 0, inserted: int = 0, updated: int = 0, skipped_dup: int = 0,
               skipped_quality: int = 0, skipped_violation: int = 0,
               errors: Optional[List[str]] = None, note: str = "") -> None:
    with get_conn() as (conn, cur):
        cur.execute(
            f"INSERT INTO kb_collect_runs (source_id, started_at, finished_at, status, fetched, "
            f"inserted, updated, skipped_dup, skipped_quality, skipped_violation, errors_json, note) "
            f"VALUES ({_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()},{_p()})",
            (source_id, started_at, finished_at, status, fetched, inserted, updated, skipped_dup,
             skipped_quality, skipped_violation, json.dumps(errors or [], ensure_ascii=False), note),
        )
        conn.commit()


def last_success(source_id: str) -> Optional[str]:
    with get_conn() as (conn, cur):
        cur.execute(
            f"SELECT finished_at FROM kb_collect_runs WHERE source_id = {_p()} AND status = 'ok' "
            f"ORDER BY finished_at DESC LIMIT 1",
            (source_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return row["finished_at"] if isinstance(row, dict) else row[0]


def recent_runs(limit: int = 50) -> List[Dict]:
    with get_conn() as (conn, cur):
        cur.execute(
            f"SELECT source_id, started_at, finished_at, status, fetched, inserted, updated, "
            f"skipped_dup, skipped_quality, skipped_violation, errors_json, note "
            f"FROM kb_collect_runs ORDER BY started_at DESC LIMIT {_p()}", (limit,))
        rows = cur.fetchall()
    cols = ["source_id", "started_at", "finished_at", "status", "fetched", "inserted", "updated",
            "skipped_dup", "skipped_quality", "skipped_violation", "errors_json", "note"]
    out = []
    for r in rows:
        out.append(dict(r) if isinstance(r, dict) else dict(zip(cols, r)))
    return out


def is_due(entry: Dict, now: Optional[datetime] = None) -> bool:
    """마지막 성공 뒤 cadence_days 가 지났으면 due(성공 기록이 없으면 due)."""
    last = last_success(entry["id"])
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return now - last_dt >= timedelta(days=int(entry.get("cadence_days") or 30))
