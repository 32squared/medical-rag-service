-- 018_coaching_tables_sqlite.sql — 웰니스 코칭 운영 테이블 (P2, SQLite)
-- 정본 18 §7.2. 러너가 ; 로 분리하므로 주석에 세미콜론 금지. BEGIN/COMMIT 미사용.
CREATE TABLE IF NOT EXISTS coaching_session (
    session_id        TEXT PRIMARY KEY,
    conversation_id   TEXT,
    mode              TEXT,
    track             TEXT,
    band_at_start     TEXT,
    consent_personal  INTEGER,
    started_at        TEXT
);
CREATE TABLE IF NOT EXISTS coaching_plan (
    plan_id              TEXT PRIMARY KEY,
    session_id           TEXT,
    track                TEXT,
    items_json           TEXT,
    target_period        TEXT,
    band_at_creation     TEXT,
    safety_banner        TEXT,
    compliance_action    TEXT,
    original_items_json  TEXT,
    created_at           TEXT
);
CREATE TABLE IF NOT EXISTS coaching_checkin (
    checkin_id  TEXT PRIMARY KEY,
    plan_id     TEXT,
    item_key    TEXT,
    done        INTEGER,
    ts          TEXT
);
CREATE INDEX IF NOT EXISTS idx_coaching_plan_session ON coaching_plan(session_id);
CREATE INDEX IF NOT EXISTS idx_coaching_checkin_plan ON coaching_checkin(plan_id);
CREATE INDEX IF NOT EXISTS idx_coaching_session_conv ON coaching_session(conversation_id);
