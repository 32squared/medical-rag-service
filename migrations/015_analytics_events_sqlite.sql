-- =============================================================================
-- 015_analytics_events_sqlite.sql — 비식별 이벤트 스토어 (개선 루프 E2, SQLite 호환)
-- 015_analytics_events.sql 의 SQLite 변형. 러너가 세미콜론 단위로 실행(BEGIN/COMMIT 생략).
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_events (
    id                  TEXT PRIMARY KEY,
    event_name          TEXT NOT NULL,
    conversation_id     TEXT,
    rag_query_id        TEXT,
    intent              TEXT,
    primary_domain      TEXT,
    risk_level          TEXT,
    guardrail_action    TEXT,
    gate_decision       TEXT,
    evidence_quality    TEXT,
    citations_count     INTEGER,
    latency_ms          INTEGER,
    is_followup         INTEGER,
    had_personal_block  INTEGER,
    gave_referral       INTEGER,
    refusal             INTEGER,
    emergency           INTEGER,
    props_json          TEXT DEFAULT '{}',
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_name ON analytics_events(event_name);
CREATE INDEX IF NOT EXISTS idx_analytics_events_conv ON analytics_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_date ON analytics_events(created_at);
