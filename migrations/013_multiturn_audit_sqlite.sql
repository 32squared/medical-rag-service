-- =============================================================================
-- 013_multiturn_audit_sqlite.sql — 멀티턴 재작성 감사 컬럼 (SQLite 호환)
-- SQLite는 ADD COLUMN IF NOT EXISTS 미지원 → 러너에서 duplicate column 무시.
-- 06-multiturn-design.md §6-4.
-- =============================================================================

ALTER TABLE rag_queries ADD COLUMN rewrite_method TEXT;
ALTER TABLE rag_queries ADD COLUMN rewritten_from TEXT;
