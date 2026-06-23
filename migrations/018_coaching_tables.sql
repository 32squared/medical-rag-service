-- =============================================================================
-- 018_coaching_tables.sql — 웰니스 코칭 운영 테이블 (P2, PostgreSQL)
-- 정본: docs/plan/18-wellness-coaching.md §7.2.
-- 최소수집: checkin=실천 bool만. 밴드는 라벨로만(캡 적용 근거). 원시값·진단명 미저장.
-- analytics 는 015 재사용(신규 event_name + props_json) — 별도 마이그레이션 없음.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS coaching_session (
    session_id        TEXT PRIMARY KEY,
    conversation_id   TEXT,           -- 조인키(내부 id, PII 아님)
    mode              TEXT,           -- medical | wellness:diet | wellness:exercise | wellness:habit
    track             TEXT,           -- diet|exercise|habit (미선택 NULL)
    band_at_start     TEXT,           -- 안정|주의|경고 라벨(원시값 아님)
    consent_personal  INTEGER,        -- 코칭 개인신호 동의 스냅샷(0/1)
    started_at        TEXT
);

CREATE TABLE IF NOT EXISTS coaching_plan (
    plan_id              TEXT PRIMARY KEY,
    session_id           TEXT,        -- FK→coaching_session
    track                TEXT,
    items_json           TEXT,        -- [{item_key, text, cite}]
    target_period        TEXT,        -- 2주|1개월|3개월+
    band_at_creation     TEXT,        -- 라벨
    safety_banner        TEXT,        -- 밴드 조건부 배너(§5.4)
    compliance_action    TEXT,        -- pass|softened|band_capped (WC-C 결과)
    original_items_json  TEXT,        -- WC-C 완화 전 원본(무변경 NULL) §5.6
    created_at           TEXT
);

CREATE TABLE IF NOT EXISTS coaching_checkin (
    checkin_id  TEXT PRIMARY KEY,
    plan_id     TEXT,                 -- FK→coaching_plan
    item_key    TEXT,
    done        INTEGER,              -- 0/1 (실천 여부만 — 밴드·원시값 미저장)
    ts          TEXT
);

CREATE INDEX IF NOT EXISTS idx_coaching_plan_session ON coaching_plan(session_id);
CREATE INDEX IF NOT EXISTS idx_coaching_checkin_plan ON coaching_checkin(plan_id);
CREATE INDEX IF NOT EXISTS idx_coaching_session_conv ON coaching_session(conversation_id);

COMMIT;
