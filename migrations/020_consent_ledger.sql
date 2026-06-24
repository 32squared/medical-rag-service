-- =============================================================================
-- 020_consent_ledger.sql — 동의원장 (P0, PostgreSQL)
-- 정본: docs/plan/23-p0-detailed-design.md §2. 런치블로커 B 핵심.
-- append-only: 레코드를 UPDATE/DELETE 하지 않는다. 철회=action 'revoke' 신규 레코드.
-- 현재 유효 상태 = 주체×항목 최신 레코드의 action. 전체 이력·감사·철회권 충족.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS consent_item (
    item_key     TEXT    NOT NULL,
    version      INTEGER NOT NULL,
    title        TEXT,
    body_url     TEXT,                 -- 동의서 본문(고지) 링크
    required     INTEGER,              -- 0/1 (필수 동의 여부)
    effective_at TEXT,
    PRIMARY KEY (item_key, version)
);

CREATE TABLE IF NOT EXISTS consent_record (
    id            TEXT PRIMARY KEY,
    subject_id    TEXT NOT NULL,       -- account.id (FK 앱 enforced)
    item_key      TEXT NOT NULL,
    item_version  INTEGER,
    action        TEXT NOT NULL,       -- grant | revoke
    source        TEXT,                -- onboarding | settings | reconsent
    created_at    TEXT NOT NULL,
    evidence_hash TEXT                 -- 고지문구+버전 해시(무엇에 동의했는지 고정)
);

CREATE INDEX IF NOT EXISTS idx_consent_record_subject
    ON consent_record(subject_id, item_key, created_at);

COMMIT;
