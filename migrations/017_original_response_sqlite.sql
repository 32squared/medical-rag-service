-- 017_original_response_sqlite.sql — rag_queries.original_response (SQLite)
-- 가드레일 전 원본 LLM 답변 보관 컬럼. 러너가 schema_migrations 로 1회만 적용.
ALTER TABLE rag_queries ADD COLUMN original_response TEXT;
