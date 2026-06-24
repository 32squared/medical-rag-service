"""
계정·세션 데이터 계층 — P0 (본인인증 후 계정·세션).

정본: docs/plan/23-p0-detailed-design.md §3 / migration 021.
- 본인인증(PASS) CI/DI 는 **해시 저장**(원본 비보관). CI 해시로 중복가입 식별.
- 세션 = refresh 해시 + 만료 + 철회(로그아웃·탈퇴 시 revoked_at).
- 탈퇴는 계정 status=withdrawn 으로만(동의원장 등 이력은 보존 — 감사·법적의무).

순수 함수(hash_ci)는 DB 없이 테스트 가능. DB 함수는 dbcommon 경유(PG/SQLite 듀얼).
"""
from __future__ import annotations

import logging
import os
import hmac
import hashlib
import uuid as _uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from dbcommon import get_conn, _p
from app_env import is_prod

logger = logging.getLogger(__name__)

_SCHEMA_ENSURED = False
_DEFAULT_REFRESH_TTL = 30 * 24 * 3600   # 30일


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ── 식별자 해시 (순수) ───────────────────────────────────────
def hash_ci(ci_raw: str, key: Optional[str] = None) -> str:
    """CI/DI 등 식별자 해시. 키 있으면 HMAC-SHA256(키는 env ACCOUNT_CI_HMAC_KEY),
    없으면 SHA256(개발 폴백 — **프로덕션은 키 필수**: 고정 국가식별자 레인보우/상관 방지)."""
    if not ci_raw:
        return ""
    k = key if key is not None else os.environ.get("ACCOUNT_CI_HMAC_KEY", "")
    raw = ci_raw.encode("utf-8")
    if k:
        return hmac.new(k.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    # 무키 폴백 — 고정 식별자 CI 에 무염 SHA256 은 상관/복원 위험.
    if is_prod():
        raise RuntimeError("ACCOUNT_CI_HMAC_KEY required in production (no keyless CI hashing)")
    logger.warning("CI HMAC key absent — SHA256 fallback (DEV ONLY, do not use in prod)")
    return hashlib.sha256(raw).hexdigest()


# ── 스키마 멱등 보장 ─────────────────────────────────────────
def ensure_account_schema() -> None:
    """계정·세션 테이블 멱등 보장 (PG/SQLite 공용). 정본 23 §3 / mig021."""
    with get_conn() as (conn, cur):
        cur.execute(
            """CREATE TABLE IF NOT EXISTS account (
                   id           TEXT PRIMARY KEY,
                   ci_hash      TEXT UNIQUE,
                   di_hash      TEXT,
                   status       TEXT NOT NULL,
                   created_at   TEXT NOT NULL,
                   withdrawn_at TEXT
               )""")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS auth_session (
                   id           TEXT PRIMARY KEY,
                   subject_id   TEXT NOT NULL,
                   refresh_hash TEXT,
                   device       TEXT,
                   issued_at    TEXT NOT NULL,
                   expires_at   TEXT NOT NULL,
                   revoked_at   TEXT
               )""")
        cur.execute(
            """CREATE INDEX IF NOT EXISTS idx_auth_session_subject
                   ON auth_session(subject_id)""")
        conn.commit()


def _ensure_once() -> None:
    global _SCHEMA_ENSURED
    if _SCHEMA_ENSURED:
        return
    try:
        ensure_account_schema()
        _SCHEMA_ENSURED = True
    except Exception:
        pass


# ── 계정 ─────────────────────────────────────────────────────
def upsert_account_by_ci(ci_hash, di_hash=None) -> Optional[str]:
    """CI 해시로 계정 식별 → 기존 있으면 그 id(중복가입), 없으면 신규 active 계정 생성."""
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT id FROM account WHERE ci_hash = {_p()}", (ci_hash,))
            row = cur.fetchone()
            if row:
                return dict(row)["id"]
            aid = _uuid.uuid4().hex
            cur.execute(
                f"INSERT INTO account (id, ci_hash, di_hash, status, created_at, withdrawn_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (aid, ci_hash, di_hash, "active", _iso(_now()), None),
            )
            conn.commit()
            return aid
    except Exception:
        return None


def get_account(account_id) -> Optional[Dict]:
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT * FROM account WHERE id = {_p()}", (account_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def withdraw_account(account_id) -> bool:
    """탈퇴 — 모든 세션 철회 + status=withdrawn. 동의원장 이력은 보존.
    세션 철회 성공 여부를 반환(False면 호출측이 5xx 로 표면화 — 철회 실패가
    조용히 'withdrawn 인데 세션 활성' 상태로 남지 않게)."""
    _ensure_once()
    try:
        revoked = revoke_all_sessions(account_id)        # 먼저 철회
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE account SET status = {_p()}, withdrawn_at = {_p()} WHERE id = {_p()}",
                ("withdrawn", _iso(_now()), account_id),
            )
            conn.commit()
        return bool(revoked)
    except Exception:
        return False


def reactivate_account(account_id) -> bool:
    """탈퇴 계정 재활성(재가입). 호출측이 재동의를 강제해야 함(이전 동의 철회)."""
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE account SET status = {_p()}, withdrawn_at = {_p()} WHERE id = {_p()}",
                ("active", None, account_id),
            )
            conn.commit()
        return True
    except Exception:
        return False


# ── 세션 ─────────────────────────────────────────────────────
def create_session(subject_id, refresh_hash, *, device=None,
                   ttl_seconds: int = _DEFAULT_REFRESH_TTL) -> Optional[str]:
    """세션 1건 생성 → session_id (issued_at·expires_at 기록)."""
    _ensure_once()
    sid = _uuid.uuid4().hex
    now = _now()
    exp = now + timedelta(seconds=ttl_seconds)
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"INSERT INTO auth_session (id, subject_id, refresh_hash, device, "
                f"issued_at, expires_at, revoked_at) "
                f"VALUES ({_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()}, {_p()})",
                (sid, subject_id, refresh_hash, device, _iso(now), _iso(exp), None),
            )
            conn.commit()
    except Exception:
        return None
    return sid


def get_active_session(session_id, now: Optional[datetime] = None) -> Optional[Dict]:
    """철회되지 않고 만료되지 않은 세션이면 dict, 아니면 None."""
    _ensure_once()
    now_iso = _iso(now or _now())
    try:
        with get_conn() as (conn, cur):
            cur.execute(f"SELECT * FROM auth_session WHERE id = {_p()}", (session_id,))
            row = cur.fetchone()
    except Exception:
        return None
    if not row:
        return None
    d = dict(row)
    if d.get("revoked_at"):
        return None
    if (d.get("expires_at") or "") <= now_iso:   # 만료
        return None
    return d


def rotate_session_refresh(session_id, old_hash, new_hash) -> bool:
    """refresh 회전 — 현재 refresh_hash 가 old 일 때만 new 로 교체(단일 라이터).
    성공 시 True. 제시된 refresh 가 현재값과 불일치(이미 회전됨=재사용)면 0행 → False."""
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE auth_session SET refresh_hash = {_p()} "
                f"WHERE id = {_p()} AND refresh_hash = {_p()} AND revoked_at IS NULL",
                (new_hash, session_id, old_hash),
            )
            updated = cur.rowcount
            conn.commit()
        return updated == 1
    except Exception:
        return False


def revoke_session(session_id) -> bool:
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE auth_session SET revoked_at = {_p()} WHERE id = {_p()} AND revoked_at IS NULL",
                (_iso(_now()), session_id),
            )
            conn.commit()
        return True
    except Exception:
        return False


def revoke_all_sessions(subject_id) -> bool:
    """주체의 모든 활성 세션 철회 (로그아웃-올 / 탈퇴)."""
    _ensure_once()
    try:
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE auth_session SET revoked_at = {_p()} "
                f"WHERE subject_id = {_p()} AND revoked_at IS NULL",
                (_iso(_now()), subject_id),
            )
            conn.commit()
        return True
    except Exception:
        return False
