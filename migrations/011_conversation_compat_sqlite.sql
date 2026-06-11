-- =============================================================================
-- 011_conversation_compat_sqlite.sql — Phoenix 대화관리 API 호환 (SQLite 페어)
-- SQLite는 ADD COLUMN IF NOT EXISTS 미지원 — migrate_runner가
-- "duplicate column" OperationalError를 멱등 처리한다.
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT,
    user_name           TEXT,
    title               TEXT,
    env                 TEXT,
    conversation_strid  TEXT,
    emergency_state     TEXT DEFAULT 'NORMAL',
    created_at          TEXT,
    updated_at          TEXT,
    display_status      TEXT DEFAULT 'ACTIVE',
    display_type        TEXT DEFAULT 'SEARCH',
    project_strid       TEXT,
    parent_conversation_strid TEXT
);

-- 기존 테이블(컬럼 누락)용 ALTER — 신규 생성 시 duplicate column으로 무시됨
ALTER TABLE conversations ADD COLUMN display_status TEXT DEFAULT 'ACTIVE';
ALTER TABLE conversations ADD COLUMN display_type   TEXT DEFAULT 'SEARCH';
ALTER TABLE conversations ADD COLUMN project_strid  TEXT;
ALTER TABLE conversations ADD COLUMN parent_conversation_strid TEXT;

CREATE INDEX IF NOT EXISTS idx_conv_user_status
    ON conversations(user_id, display_status);
CREATE INDEX IF NOT EXISTS idx_conv_updated
    ON conversations(updated_at);
