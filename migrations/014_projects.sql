-- =============================================================================
-- 014_projects.sql — Phoenix 대화관리 Projects API 호환 테이블 (PostgreSQL)
-- Conversations_20260608.pdf §6~9 (List/Create/Update/Delete projects).
-- conversations.project_strid 가 이 테이블의 strid 를 참조한다(느슨한 참조).
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
