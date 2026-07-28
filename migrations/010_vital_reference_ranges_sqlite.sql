-- =============================================================================
-- 010_vital_reference_ranges_sqlite.sql — 생체신호·환경 공인 참조범위 (SQLite 페어)
-- PostgreSQL 버전(010_vital_reference_ranges.sql)과 동일 스키마.
-- =============================================================================

CREATE TABLE IF NOT EXISTS vital_reference_ranges (
    id              TEXT PRIMARY KEY,
    signal_key      TEXT NOT NULL,
    population      TEXT NOT NULL DEFAULT 'adult',
    locale          TEXT NOT NULL DEFAULT 'KR',
    unit            TEXT NOT NULL,
    ranges_json     TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    source_url      TEXT,
    source_version  TEXT,
    effective_date  TEXT,
    notes           TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vital_ref_signal
    ON vital_reference_ranges(signal_key, locale, population);
