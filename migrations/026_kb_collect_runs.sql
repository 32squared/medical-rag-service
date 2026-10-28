-- 026_kb_collect_runs.sql — KB 자동 구축 실행 기록 (kb_collect.ledger)
-- 대상: PostgreSQL. SQLite 는 026_kb_collect_runs_sqlite.sql
CREATE TABLE IF NOT EXISTS kb_collect_runs (
    id                 BIGSERIAL PRIMARY KEY,
    source_id          TEXT NOT NULL,
    started_at         TEXT NOT NULL,
    finished_at        TEXT NOT NULL,
    status             TEXT NOT NULL,          -- ok | empty | fetch_error | not_implemented
    fetched            INTEGER NOT NULL DEFAULT 0,
    inserted           INTEGER NOT NULL DEFAULT 0,
    updated            INTEGER NOT NULL DEFAULT 0,
    skipped_dup        INTEGER NOT NULL DEFAULT 0,
    skipped_quality    INTEGER NOT NULL DEFAULT 0,
    skipped_violation  INTEGER NOT NULL DEFAULT 0,
    errors_json        TEXT NOT NULL DEFAULT '[]',
    note               TEXT
);
CREATE INDEX IF NOT EXISTS idx_kb_collect_runs_source ON kb_collect_runs(source_id, finished_at DESC);
