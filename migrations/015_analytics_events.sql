-- =============================================================================
-- 015_analytics_events.sql — 비식별 이벤트 스토어 (개선 루프 E2, PostgreSQL)
-- 대화 1턴 = 1 이벤트(라벨·카운트·불리언만). 질의원문·원시수치·진단명·PII 미저장.
-- BI(Metabase/Grafana)는 이 테이블만 조회 — rag_queries(원문 보유)는 미조회.
-- 정본: docs/ontology/feedback-ontology.ttl (phr:EventStore / phr:AnalyticsEvent).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS analytics_events (
    id                  TEXT PRIMARY KEY,
    event_name          TEXT NOT NULL,        -- answer_shown | insufficient_evidence | emergency_redirect | triage_clarify
    conversation_id     TEXT,                 -- 조인 키(내부 id, PII 아님)
    rag_query_id        TEXT,                 -- 감사 로그(rag_queries) 링크, 옵션
    -- 비식별 차원 (라벨)
    intent              TEXT,
    primary_domain      TEXT,
    risk_level          TEXT,
    guardrail_action    TEXT,
    gate_decision       TEXT,
    evidence_quality    TEXT,
    -- 카운트
    citations_count     INTEGER,
    latency_ms          INTEGER,
    -- 불리언 (0/1)
    is_followup         INTEGER,
    had_personal_block  INTEGER,
    gave_referral       INTEGER,
    refusal             INTEGER,               -- 거절수요(E4) 신호
    emergency           INTEGER,
    props_json          TEXT DEFAULT '{}',     -- 향후 비식별 속성 확장용
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_name ON analytics_events(event_name);
CREATE INDEX IF NOT EXISTS idx_analytics_events_conv ON analytics_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_date ON analytics_events(created_at);

COMMIT;
