-- =============================================================================
-- 016_response_feedback_sqlite.sql — 답변 명시 피드백(👍/👎) (SQLite 호환)
-- 016_response_feedback.sql 의 SQLite 변형. 러너가 세미콜론 단위로 실행(BEGIN/COMMIT 생략).
-- 주의: 주석에 세미콜론 금지(러너가 세미콜론으로 split).
-- =============================================================================

CREATE TABLE IF NOT EXISTS response_feedback (
    id                  TEXT PRIMARY KEY,
    rag_query_id        TEXT,
    conversation_id     TEXT,
    user_id             TEXT,
    rating              TEXT NOT NULL,
    reason_code         TEXT,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_response_feedback_query ON response_feedback(rag_query_id);
CREATE INDEX IF NOT EXISTS idx_response_feedback_date ON response_feedback(created_at);
