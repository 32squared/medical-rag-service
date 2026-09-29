"""routine_repo.py — 루틴 프로그램 영속 계층(팩 기반, 기본 = 건강 12주).

정본: docs/plan/25-routine-transition-spec.md §E(데이터 모델)·§F(API 계약).

설계:
  - 스키마는 migrations/023 + **in-code 멱등 ensure**(러너 미적용 대비, rag_db 관례).
  - 개인별 격리 키 = subject_id(= account_id = conversation_id).
  - 파생값(주차·스트릭·adherence)은 **전부 서버에서 결정적으로 계산**(E-3).
  - 저장 금지: 원시 측정값·진단명. value 는 선택지 라벨만.
  - 프로그램은 시작 시점의 (pack_id, pack_version, weeks_total) 을 저장하고 그 값으로
    진도를 계산한다(28 루틴 팩 플랫폼). 기존 행은 기본값 = health_12w v1 · 12주.
  - 모든 함수는 실패해도 예외를 밖으로 던지지 않는다(조회=빈값, 쓰기=None/False).
    루틴은 매일 쓰는 화면이라 부분 실패가 화면 전체를 깨면 안 된다.
"""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from dbcommon import get_conn, _p, _row_to_dict

KST = timezone(timedelta(hours=9))
_SCHEMA_ENSURED = False


# ── 시간 유틸(KST 고정 — Cloud Run 은 UTC) ─────────────────────────
def today_kst() -> str:
    return datetime.now(timezone.utc).astimezone(KST).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _d(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d")
    except Exception:
        return None


def days_between(a: str, b: str) -> int:
    """a → b 일수(b - a). 파싱 실패 시 0."""
    da, db = _d(a), _d(b)
    return (db - da).days if (da and db) else 0


def add_days(d: str, n: int) -> str:
    dt = _d(d)
    return (dt + timedelta(days=n)).strftime("%Y-%m-%d") if dt else d


# ── 스키마 ────────────────────────────────────────────────────────
_DDL = [
    """CREATE TABLE IF NOT EXISTS routine_program (
           program_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, plan_id TEXT,
           track TEXT NOT NULL, focus TEXT, anchor TEXT, intake_json TEXT,
           band_at_start TEXT, item_cap INTEGER DEFAULT 0, started_on TEXT NOT NULL,
           current_week INTEGER DEFAULT 1, weeks_total INTEGER DEFAULT 12,
           status TEXT DEFAULT 'active', mode TEXT DEFAULT 'daily',
           adherence_state TEXT DEFAULT 'active', paused_days INTEGER DEFAULT 0,
           paused_until TEXT, freeze_used_on TEXT, week_state_json TEXT,
           nudge_sent_json TEXT, curriculum_version INTEGER DEFAULT 1,
           last_seen_on TEXT, completed_on TEXT, created_at TEXT, updated_at TEXT,
           pack_id TEXT DEFAULT 'health_12w', pack_version INTEGER DEFAULT 1)""",
    # 025 — 팩 컬럼(기존 DB 는 ALTER, 이미 있으면 실패를 무시)
    "ALTER TABLE routine_program ADD COLUMN pack_id TEXT DEFAULT 'health_12w'",
    "ALTER TABLE routine_program ADD COLUMN pack_version INTEGER DEFAULT 1",
    "CREATE INDEX IF NOT EXISTS ix_routine_program_subject ON routine_program (subject_id, status)",
    """CREATE TABLE IF NOT EXISTS routine_checkin (
           checkin_id TEXT PRIMARY KEY, program_id TEXT NOT NULL, subject_id TEXT NOT NULL,
           action_date TEXT NOT NULL, week_no INTEGER, slot TEXT NOT NULL,
           item_key TEXT NOT NULL, status TEXT NOT NULL, value TEXT, barrier TEXT,
           undo_count INTEGER DEFAULT 0, idempotency_key TEXT, client_ts TEXT,
           created_at TEXT, updated_at TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_routine_checkin_day ON routine_checkin (program_id, action_date, item_key)",
    "CREATE INDEX IF NOT EXISTS ix_routine_checkin_subject_date ON routine_checkin (subject_id, action_date)",
    """CREATE TABLE IF NOT EXISTS routine_report (
           program_id TEXT NOT NULL, week_no INTEGER NOT NULL, done_days INTEGER,
           goal_days INTEGER, adherence INTEGER, streak_end INTEGER, na_days INTEGER,
           badges_json TEXT, transition TEXT, generated_at TEXT, read_at TEXT,
           PRIMARY KEY (program_id, week_no))""",
    """CREATE TABLE IF NOT EXISTS routine_notify_pref (
           subject_id TEXT PRIMARY KEY, hhmm TEXT, channel TEXT,
           push_granted INTEGER DEFAULT 0, updated_at TEXT)""",
]


def ensure_schema() -> None:
    """멱등 스키마 보장. 각 DDL 을 독립 트랜잭션으로(PG 는 실패문이 트랜잭션을 오염)."""
    for ddl in _DDL:
        try:
            with get_conn() as (conn, cur):
                cur.execute(ddl)
                conn.commit()
        except Exception:
            pass


def _ensure() -> None:
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    try:
        ensure_schema()
        _SCHEMA_ENSURED = True
    except Exception:
        pass          # 다음 호출에서 재시도


# ── 프로그램 ──────────────────────────────────────────────────────
_PROG_COLS = ("program_id, subject_id, plan_id, track, focus, anchor, intake_json, "
              "band_at_start, item_cap, started_on, current_week, weeks_total, status, "
              "mode, adherence_state, paused_days, paused_until, freeze_used_on, "
              "week_state_json, nudge_sent_json, curriculum_version, last_seen_on, completed_on, "
              "pack_id, pack_version")


def get_active_program(subject_id: str) -> Optional[Dict]:
    """활성(active|paused) 프로그램 1건. 없으면 None."""
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT {_PROG_COLS} FROM routine_program "
                f"WHERE subject_id = {_p()} AND status IN ('active','paused') "
                f"ORDER BY created_at DESC LIMIT 1", (subject_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


def get_program(program_id: str) -> Optional[Dict]:
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT {_PROG_COLS} FROM routine_program WHERE program_id = {_p()}",
                        (program_id,))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


def create_program(*, subject_id: str, track: str, plan_id: Optional[str] = None,
                   focus: Optional[str] = None, anchor: Optional[str] = None,
                   intake: Optional[Dict] = None, band: Optional[str] = None,
                   item_cap: int = 0, started_on: Optional[str] = None,
                   curriculum_version: int = 1, pack_id: str = "health_12w",
                   pack_version: int = 1, weeks_total: int = 12) -> Optional[str]:
    """프로그램 생성 → program_id. 실패 시 None."""
    _ensure()
    pid = _uuid.uuid4().hex
    now, day = now_iso(), (started_on or today_kst())
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO routine_program (program_id, subject_id, plan_id, track, focus, "
                f"anchor, intake_json, band_at_start, item_cap, started_on, current_week, "
                f"weeks_total, status, mode, adherence_state, paused_days, curriculum_version, "
                f"last_seen_on, created_at, updated_at, pack_id, pack_version) VALUES ("
                + ", ".join([_p()] * 22) + ")",
                (pid, subject_id, plan_id, track, focus, anchor,
                 json.dumps(intake or {}, ensure_ascii=False), band, int(item_cap), day,
                 1, int(weeks_total), "active", "daily", "active", 0, int(curriculum_version),
                 day, now, now, pack_id, int(pack_version)))
            conn.commit()
        return pid
    except Exception:
        return None


def update_program(program_id: str, **fields) -> bool:
    """허용 컬럼만 부분 업데이트."""
    _ensure()
    allowed = {"plan_id", "focus", "anchor", "band_at_start", "item_cap", "current_week",
               "status", "mode", "adherence_state", "paused_days", "paused_until",
               "freeze_used_on", "week_state_json", "nudge_sent_json", "last_seen_on",
               "completed_on", "started_on", "track", "intake_json"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = {_p()}")
            vals.append(v)
    if not sets:
        return False
    sets.append(f"updated_at = {_p()}")
    vals.append(now_iso())
    vals.append(program_id)
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"UPDATE routine_program SET {', '.join(sets)} WHERE program_id = {_p()}",
                        tuple(vals))
            conn.commit()
        return True
    except Exception:
        return False


def archive_all(subject_id: str) -> bool:
    """탈퇴/트랙변경 시 기존 프로그램 보관 처리."""
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE routine_program SET status = 'archived', updated_at = {_p()} "
                f"WHERE subject_id = {_p()} AND status IN ('active','paused')",
                (now_iso(), subject_id))
            conn.commit()
        return True
    except Exception:
        return False


# ── 체크인 ────────────────────────────────────────────────────────
def get_checkin(program_id: str, action_date: str, item_key: str) -> Optional[Dict]:
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT checkin_id, status, value, barrier, undo_count, created_at "
                f"FROM routine_checkin WHERE program_id = {_p()} AND action_date = {_p()} "
                f"AND item_key = {_p()}", (program_id, action_date, item_key))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


def upsert_checkin(*, program_id: str, subject_id: str, action_date: str, week_no: int,
                   slot: str, item_key: str, status: str, value: Optional[str] = None,
                   barrier: Optional[str] = None, idempotency_key: Optional[str] = None,
                   client_ts: Optional[str] = None) -> Optional[Dict]:
    """하루-항목 1행 upsert(멱등). 반환 {checkin_id, duplicate, undo_count} 또는 None.

    UNIQUE(program_id, action_date, item_key) 로 중복 체크인이 구조적으로 불가능하다.
    실행취소는 append 가 아니라 같은 행의 status='undone' UPDATE(스펙 C13).
    """
    _ensure()
    existing = get_checkin(program_id, action_date, item_key)
    now = now_iso()
    try:
        if existing:
            undo = int(existing.get("undo_count") or 0) + (1 if status == "undone" else 0)
            with get_conn() as (conn, cur):
                cur.execute(
                    f"UPDATE routine_checkin SET status = {_p()}, value = {_p()}, "
                    f"barrier = {_p()}, undo_count = {_p()}, updated_at = {_p()} "
                    f"WHERE program_id = {_p()} AND action_date = {_p()} AND item_key = {_p()}",
                    (status, value, barrier, undo, now, program_id, action_date, item_key))
                conn.commit()
            return {"checkin_id": existing.get("checkin_id"), "duplicate": True, "undo_count": undo}
        cid = _uuid.uuid4().hex
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO routine_checkin (checkin_id, program_id, subject_id, action_date, "
                f"week_no, slot, item_key, status, value, barrier, undo_count, idempotency_key, "
                f"client_ts, created_at, updated_at) VALUES (" + ", ".join([_p()] * 15) + ")",
                (cid, program_id, subject_id, action_date, int(week_no or 1), slot, item_key,
                 status, value, barrier, 0, idempotency_key, client_ts, now, now))
            conn.commit()
        return {"checkin_id": cid, "duplicate": False, "undo_count": 0}
    except Exception:
        # UNIQUE 경합(동시 탭) → 이미 들어간 행을 사실로 인정
        again = get_checkin(program_id, action_date, item_key)
        if again:
            return {"checkin_id": again.get("checkin_id"), "duplicate": True,
                    "undo_count": int(again.get("undo_count") or 0)}
        return None


def list_checkins(program_id: str, *, slot: Optional[str] = None,
                  since: Optional[str] = None) -> List[Dict]:
    """프로그램의 체크인 목록(날짜 오름차순)."""
    _ensure()
    sql = (f"SELECT action_date, week_no, slot, item_key, status, value, barrier "
           f"FROM routine_checkin WHERE program_id = {_p()}")
    args: List = [program_id]
    if slot:
        sql += f" AND slot = {_p()}"
        args.append(slot)
    if since:
        sql += f" AND action_date >= {_p()}"
        args.append(since)
    sql += " ORDER BY action_date"
    try:
        with get_conn() as (conn, cur):
            cur.execute(sql, tuple(args))
            return [_row_to_dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def done_dates(subject_id: str) -> List[str]:
    """계정 단위 done 날짜(오름차순, 중복 제거) — 스트릭 계산용(스펙 C8)."""
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT DISTINCT action_date FROM routine_checkin "
                f"WHERE subject_id = {_p()} AND status = 'done' ORDER BY action_date",
                (subject_id,))
            return [(_row_to_dict(r) or {}).get("action_date") for r in cur.fetchall()]
    except Exception:
        return []


def days_since_last_checkin(subject_id: str) -> int:
    """마지막 done 이후 경과일. 기록이 없으면 0(넛지 오발동 방지)."""
    ds = [d for d in done_dates(subject_id) if d]
    if not ds:
        return 0
    return max(0, days_between(ds[-1], today_kst()))


# ── 파생 계산(결정적, 서버 단일 진실원천 — 스펙 E-3) ────────────────
def streak_from(dates: List[str], today: Optional[str] = None) -> int:
    """오늘(또는 어제)부터 역순 연속 일수. 오늘 미체크여도 어제까지 이어졌으면 유지."""
    s = {d for d in (dates or []) if d}
    if not s:
        return 0
    t = today or today_kst()
    cur = t if t in s else add_days(t, -1)
    if cur not in s:
        return 0
    n = 0
    while cur in s:
        n += 1
        cur = add_days(cur, -1)
    return n


def best_streak(dates: List[str]) -> int:
    s = sorted({d for d in (dates or []) if d})
    if not s:
        return 0
    best = run = 1
    for i in range(1, len(s)):
        run = run + 1 if days_between(s[i - 1], s[i]) == 1 else 1
        best = max(best, run)
    return best


def weeks_total_of(program: Optional[Dict]) -> int:
    """프로그램 기간(주). 컬럼이 비었거나 이상하면 12(건강 팩 기본)."""
    try:
        n = int((program or {}).get("weeks_total") or 12)
    except (TypeError, ValueError):
        return 12
    return max(1, min(52, n))


def week_of(started_on: str, action_date: str, paused_days: int = 0,
            weeks_total: int = 12) -> int:
    """행동일이 속한 주차(1-base). 일시정지 일수는 진도에서 제외."""
    n = days_between(started_on, action_date) - max(0, int(paused_days or 0))
    return max(1, min(int(weeks_total or 12), n // 7 + 1))


def current_week(program: Dict, today: Optional[str] = None) -> int:
    if not program:
        return 1
    return week_of(program.get("started_on") or today_kst(), today or today_kst(),
                   int(program.get("paused_days") or 0), weeks_total_of(program))


def day_no(program: Dict, today: Optional[str] = None) -> int:
    if not program:
        return 1
    n = days_between(program.get("started_on") or today_kst(), today or today_kst())
    return max(1, n - max(0, int(program.get("paused_days") or 0)) + 1)


def week_stats(program: Dict, week_no: int, goal: int) -> Dict:
    """주차 실천 집계.

    goal_days = 커리큘럼 목표(표시용, 불변). na('해당없음') 날은 사용자 탓이 아니므로
    **실천율 분모에서만** 차감한다(eff_goal). 표시 목표까지 줄이면 '4/2' 같은 표기가 된다.
    """
    pid = (program or {}).get("program_id")
    started = (program or {}).get("started_on") or today_kst()
    paused = int((program or {}).get("paused_days") or 0)
    total = weeks_total_of(program)
    done, na = set(), set()
    for c in list_checkins(pid, slot="main"):
        d = c.get("action_date")
        if not d or week_of(started, d, paused, total) != week_no:
            continue
        if c.get("status") == "done":
            done.add(d)
        elif c.get("status") == "na":
            na.add(d)
    g = max(1, int(goal or 1))
    eff = max(1, g - len(na))
    return {"done_days": len(done), "goal_days": g, "eff_goal": eff, "na_days": len(na),
            "adherence": min(100, round(len(done) / eff * 100))}


def program_adherence(program: Dict) -> int:
    """전체 실천율 = done / (done + skip). na 제외."""
    pid = (program or {}).get("program_id")
    d = s = 0
    for c in list_checkins(pid):
        st = c.get("status")
        if st == "done":
            d += 1
        elif st == "skip":
            s += 1
    return round(d / (d + s) * 100) if (d + s) else 0


def build_week_state(program: Dict, cur_week: int, pack=None) -> List[Dict]:
    """전체 주차 진도 배열 — 프론트 타임라인/히트맵 소스. pack 없으면 프로그램의 팩."""
    import routine_engine as eng
    import routine_packs as rp
    pk = pack or rp.for_program(program)
    out = []
    for w in range(1, weeks_total_of(program) + 1):
        g = eng.goal_days(w, pk)
        if w < cur_week:
            st = week_stats(program, w, g)
            state = "done" if st["done_days"] >= st["eff_goal"] else "past"
        elif w == cur_week:
            st = week_stats(program, w, g)
            state = "now"
        else:
            st = {"done_days": 0, "goal_days": g, "eff_goal": g, "na_days": 0, "adherence": 0}
            state = "future"
        out.append({"w": w, "state": state, "done_days": st["done_days"],
                    "goal_days": st["goal_days"], "theme": eng.week_meta(w, pk).get("theme", "")})
    return out


def week_days(program: Dict, cur_week: int) -> List[Dict]:
    """이번 주 7일 점 상태(월~일 표시용)."""
    started = (program or {}).get("started_on") or today_kst()
    paused = int((program or {}).get("paused_days") or 0)
    base = add_days(started, (cur_week - 1) * 7 + paused)
    marks = {}
    for c in list_checkins((program or {}).get("program_id"), slot="main"):
        if c.get("action_date"):
            marks[c["action_date"]] = c.get("status")
    wd = ["월", "화", "수", "목", "금", "토", "일"]
    out, today = [], today_kst()
    for i in range(7):
        d = add_days(base, i)
        dt = _d(d)
        st = marks.get(d)
        state = ("done" if st == "done" else "skip" if st == "skip" else
                 "na" if st == "na" else "today" if d == today else
                 "future" if days_between(today, d) > 0 else "missed")
        out.append({"date": d, "weekday": wd[dt.weekday()] if dt else "", "state": state})
    return out


def heat_days(program: Dict) -> List[Dict]:
    """전체 기간 히트맵(level 0~2)."""
    started = (program or {}).get("started_on") or today_kst()
    marks = {}
    for c in list_checkins((program or {}).get("program_id")):
        d = c.get("action_date")
        if not d:
            continue
        lv = 2 if c.get("status") == "done" else 1 if c.get("status") in ("skip", "na") else 0
        marks[d] = max(marks.get(d, 0), lv)
    out, today = [], today_kst()
    n = max(0, days_between(started, today))
    for i in range(min(n + 1, weeks_total_of(program) * 7)):
        d = add_days(started, i)
        out.append({"date": d, "level": marks.get(d, 0)})
    return out


# ── 주간 리포트 ───────────────────────────────────────────────────
def save_report(*, program_id: str, week_no: int, done_days: int, goal_days: int,
                adherence: int, streak_end: int, na_days: int = 0,
                badges: Optional[List[str]] = None, transition: str = "hold") -> bool:
    _ensure()
    now = now_iso()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT week_no FROM routine_report WHERE program_id = {_p()} "
                        f"AND week_no = {_p()}", (program_id, int(week_no)))
            if cur.fetchone():
                cur.execute(
                    f"UPDATE routine_report SET done_days={_p()}, goal_days={_p()}, "
                    f"adherence={_p()}, streak_end={_p()}, na_days={_p()}, badges_json={_p()}, "
                    f"transition={_p()} WHERE program_id={_p()} AND week_no={_p()}",
                    (done_days, goal_days, adherence, streak_end, na_days,
                     json.dumps(badges or [], ensure_ascii=False), transition,
                     program_id, int(week_no)))
            else:
                cur.execute(
                    f"INSERT INTO routine_report (program_id, week_no, done_days, goal_days, "
                    f"adherence, streak_end, na_days, badges_json, transition, generated_at) "
                    f"VALUES (" + ", ".join([_p()] * 10) + ")",
                    (program_id, int(week_no), done_days, goal_days, adherence, streak_end,
                     na_days, json.dumps(badges or [], ensure_ascii=False), transition, now))
            conn.commit()
        return True
    except Exception:
        return False


def get_report(program_id: str, week_no: int) -> Optional[Dict]:
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT week_no, done_days, goal_days, adherence, streak_end, na_days, "
                f"badges_json, transition, generated_at, read_at FROM routine_report "
                f"WHERE program_id = {_p()} AND week_no = {_p()}", (program_id, int(week_no)))
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    except Exception:
        return None


def mark_report_read(program_id: str, week_no: int) -> bool:
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"UPDATE routine_report SET read_at = {_p()} WHERE program_id = {_p()} "
                        f"AND week_no = {_p()}", (now_iso(), program_id, int(week_no)))
            conn.commit()
        return True
    except Exception:
        return False


def unread_report_week(program_id: str, before_week: int) -> Optional[int]:
    """가장 오래된 미열람 리포트 주차(현재 주차 이전만)."""
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"SELECT week_no FROM routine_report WHERE program_id = {_p()} "
                f"AND (read_at IS NULL OR read_at = '') AND week_no < {_p()} "
                f"ORDER BY week_no LIMIT 1", (program_id, int(before_week)))
            row = cur.fetchone()
            d = _row_to_dict(row) if row else None
            return int(d["week_no"]) if d else None
    except Exception:
        return None


# ── 알림 시각 ─────────────────────────────────────────────────────
def get_notify(subject_id: str) -> Dict:
    _ensure()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT hhmm, channel, push_granted FROM routine_notify_pref "
                        f"WHERE subject_id = {_p()}", (subject_id,))
            row = cur.fetchone()
            d = _row_to_dict(row) if row else None
            if d:
                return {"hhmm": d.get("hhmm"), "channel": d.get("channel") or "inapp"}
    except Exception:
        pass
    return {"hhmm": None, "channel": "inapp"}


def set_notify(subject_id: str, hhmm: str, channel: str = "inapp") -> bool:
    _ensure()
    now = now_iso()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT subject_id FROM routine_notify_pref WHERE subject_id = {_p()}",
                        (subject_id,))
            if cur.fetchone():
                cur.execute(f"UPDATE routine_notify_pref SET hhmm = {_p()}, channel = {_p()}, "
                            f"updated_at = {_p()} WHERE subject_id = {_p()}",
                            (hhmm, channel, now, subject_id))
            else:
                cur.execute(f"INSERT INTO routine_notify_pref (subject_id, hhmm, channel, "
                            f"push_granted, updated_at) VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                            (subject_id, hhmm, channel, 0, now))
            conn.commit()
        return True
    except Exception:
        return False
