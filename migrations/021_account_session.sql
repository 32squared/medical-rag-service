-- =============================================================================
-- 021_account_session.sql — 계정·세션 (P0, PostgreSQL)
-- 정본: docs/plan/23-p0-detailed-design.md §3.
-- 본인인증(PASS) CI/DI 는 해시 저장(원본 비보관). 세션=refresh 해시·만료·철회.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS account (
    id           TEXT PRIMARY KEY,
    ci_hash      TEXT UNIQUE,          -- 연계정보(CI) 해시 — 중복가입 식별
    di_hash      TEXT,                 -- DI(서비스별) 해시
    status       TEXT NOT NULL,        -- active | dormant | withdrawn
    created_at   TEXT NOT NULL,
    withdrawn_at TEXT
);

CREATE TABLE IF NOT EXISTS auth_session (
    id           TEXT PRIMARY KEY,
    subject_id   TEXT NOT NULL,        -- account.id (FK 앱 enforced)
    refresh_hash TEXT,                 -- refresh 토큰 해시(원본 비보관)
    device       TEXT,
    issued_at    TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    revoked_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_session_subject ON auth_session(subject_id);

COMMIT;
