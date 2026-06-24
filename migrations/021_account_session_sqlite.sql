-- 021_account_session_sqlite.sql — 계정·세션 (P0, SQLite)
-- 정본 23 §3. CI/DI 해시 저장(원본 비보관). 러너가 세미콜론으로 분리하므로 주석에 세미콜론 금지.
CREATE TABLE IF NOT EXISTS account (
    id           TEXT PRIMARY KEY,
    ci_hash      TEXT UNIQUE,
    di_hash      TEXT,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    withdrawn_at TEXT
);
CREATE TABLE IF NOT EXISTS auth_session (
    id           TEXT PRIMARY KEY,
    subject_id   TEXT NOT NULL,
    refresh_hash TEXT,
    device       TEXT,
    issued_at    TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    revoked_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_session_subject ON auth_session(subject_id);
