-- =============================================================================
-- 016_response_feedback.sql — 답변 명시 피드백(👍/👎) (개선 루프 B/E, PostgreSQL)
-- 사용자 명시 피드백 1건 = 1행. rating·reason_code(코드)만 저장 — 코멘트 원문 미저장(비식별).
-- 비식별 thumbs 이벤트는 analytics_events로 별도 emit(집계용).
-- 정본: docs/ontology/feedback-ontology.ttl (phr:ExplicitFeedback).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS response_feedback (
    id                  TEXT PRIMARY KEY,
    rag_query_id        TEXT,                 -- 대상 답변(rag_queries.id)
    conversation_id     TEXT,
    user_id             TEXT,
    rating              TEXT NOT NULL,        -- up | down
    reason_code         TEXT,                 -- 비식별 코드(inaccurate|unhelpful|too_long 등), 원문 아님
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_response_feedback_query ON response_feedback(rag_query_id);
CREATE INDEX IF NOT EXISTS idx_response_feedback_date ON response_feedback(created_at);

COMMIT;
