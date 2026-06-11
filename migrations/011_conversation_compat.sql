-- =============================================================================
-- 011_conversation_compat.sql — Phoenix 대화관리 API 호환 보강 (PostgreSQL)
-- 계약: docs/api/COMPAT-conversations.md (/api/data_management/conversations)
-- 멱등성: IF NOT EXISTS. projects 기능은 보류 — project_strid 컬럼만 예약.
--
-- 참고: conversations는 호스트(테스트 시스템) 소유 테이블이지만, 독립 배포에서
-- 이력 API를 서빙하려면 RAG DB에도 존재해야 한다. 기존 행/컬럼은 변경하지 않는
-- additive ALTER만 수행한다(분리 불변식 준수).
-- =============================================================================

-- 독립 RAG DB에 conversations가 없는 경우 대비 (호스트 DB에는 이미 존재 → no-op)
CREATE TABLE IF NOT EXISTS conversations (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT,
    user_name           TEXT,
    title               TEXT,
    env                 TEXT,
    conversation_strid  TEXT,
    emergency_state     TEXT DEFAULT 'NORMAL',
    created_at          TEXT,
    updated_at          TEXT
);

-- Phoenix 호환 컬럼 (additive)
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS display_status TEXT DEFAULT 'ACTIVE';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS display_type   TEXT DEFAULT 'SEARCH';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS project_strid  TEXT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS parent_conversation_strid TEXT;

CREATE INDEX IF NOT EXISTS idx_conv_user_status
    ON conversations(user_id, display_status);
CREATE INDEX IF NOT EXISTS idx_conv_updated
    ON conversations(updated_at);
