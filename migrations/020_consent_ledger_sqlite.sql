-- 020_consent_ledger_sqlite.sql — 동의원장 (P0, SQLite)
-- 정본 23 §2. append-only(철회=revoke 신규레코드). 러너가 세미콜론으로 분리하므로 주석에 세미콜론 금지.
CREATE TABLE IF NOT EXISTS consent_item (
    item_key     TEXT    NOT NULL,
    version      INTEGER NOT NULL,
    title        TEXT,
    body_url     TEXT,
    required     INTEGER,
    effective_at TEXT,
    PRIMARY KEY (item_key, version)
);
CREATE TABLE IF NOT EXISTS consent_record (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL,
    item_key      TEXT NOT NULL,
    item_version  INTEGER,
    action        TEXT NOT NULL,
    source        TEXT,
    created_at    TEXT NOT NULL,
    evidence_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_consent_record_subject ON consent_record(subject_id, item_key, created_at);
