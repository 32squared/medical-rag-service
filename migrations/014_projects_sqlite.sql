-- =============================================================================
-- 014_projects_sqlite.sql — Projects API 호환 테이블 (SQLite 페어)
-- Conversations_20260608.pdf §6~9.
-- =============================================================================

CREATE TABLE IF NOT EXISTS rag_projects (
    strid              TEXT PRIMARY KEY,
    user_id            TEXT,
    name               TEXT,
    display_status     TEXT DEFAULT 'ACTIVE',
    creation_time      TEXT,
    last_modified_time TEXT
);

CREATE INDEX IF NOT EXISTS idx_rag_projects_user
    ON rag_projects(user_id, display_status);
