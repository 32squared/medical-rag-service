-- =============================================================================
-- 017_original_response.sql — 가드레일 전 '원본 LLM 답변' 보관 (감사·과차단 디버깅, PostgreSQL)
-- blocked(거부문 대체)·regenerated·regenerated_citation 시 LLM이 원래 생성한 답변을 보관한다.
-- pass(무변경)는 NULL. response_text 는 사용자에게 보낸 최종본 그대로 유지.
-- =============================================================================

BEGIN;

ALTER TABLE rag_queries ADD COLUMN IF NOT EXISTS original_response TEXT;

COMMIT;
