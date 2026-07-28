-- =============================================================================
-- 013_multiturn_audit.sql — 멀티턴 후속질의 재작성 감사 컬럼 (PostgreSQL)
-- 06-multiturn-design.md §6-4: 재작성 추적(원 질의 해시·재작성 방법).
-- =============================================================================

ALTER TABLE rag_queries ADD COLUMN IF NOT EXISTS rewrite_method TEXT;
ALTER TABLE rag_queries ADD COLUMN IF NOT EXISTS rewritten_from TEXT;
