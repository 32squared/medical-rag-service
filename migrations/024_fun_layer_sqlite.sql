-- (SQLite 판 — DDL 은 PG 와 동일 문법으로 작성되어 그대로 사용)
-- 024 — 오늘의 나 재미 레이어(3트랙 일일 지표·아키타입·공유 카드·웰니스 타입·월간 희귀도).
-- 정본 docs/design/todays-me-mockups/02-dev-requirements.md §3. 기존 routine_* 테이블은 건드리지 않는다.
-- 저장 금지 원칙 유지: 검진 수치(혈압·혈당)·밴드 라벨은 이 테이블들에 넣지 않는다(band_snapshot 은 컬렉션 제외 판정용 라벨만).
-- 러너가 세미콜론으로 분리해 각 문을 try/except 하므로 재적용 안전. 주석에 세미콜론 리터럴 금지.

CREATE TABLE IF NOT EXISTS daily_metrics (
    subject_id      TEXT NOT NULL,
    metric_date     TEXT NOT NULL,
    water_cups      INTEGER DEFAULT 0,
    steps           INTEGER,
    steps_source    TEXT DEFAULT 'none',
    steps_synced_at TEXT,
    steps_confirmed INTEGER DEFAULT 0,
    mind_seconds    INTEGER DEFAULT 0,
    mind_sessions   INTEGER DEFAULT 0,
    bedtime_at      TEXT,
    band_snapshot   TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    PRIMARY KEY (subject_id, metric_date)
);

CREATE INDEX IF NOT EXISTS ix_daily_metrics_subject ON daily_metrics (subject_id, metric_date);

CREATE TABLE IF NOT EXISTS archetype_result (
    subject_id       TEXT NOT NULL,
    metric_date      TEXT NOT NULL,
    archetype_id     TEXT NOT NULL,
    completed_tracks TEXT NOT NULL,
    rarity_pct       INTEGER,
    reveal_seen_at   TEXT,
    created_at       TEXT,
    updated_at       TEXT,
    PRIMARY KEY (subject_id, metric_date)
);

CREATE TABLE IF NOT EXISTS share_card (
    card_id          TEXT PRIMARY KEY,
    subject_id       TEXT NOT NULL,
    metric_date      TEXT NOT NULL,
    archetype_id     TEXT NOT NULL,
    theme_id         TEXT DEFAULT 'coral',
    stickers_json    TEXT DEFAULT '[]',
    comment          TEXT,
    hide_numbers     INTEGER DEFAULT 0,
    metrics_snapshot TEXT NOT NULL,
    rarity_pct       INTEGER,
    locked_at        TEXT,
    created_at       TEXT,
    updated_at       TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_share_card_day ON share_card (subject_id, metric_date);

CREATE TABLE IF NOT EXISTS wellness_type (
    subject_id    TEXT PRIMARY KEY,
    type_id       TEXT NOT NULL,
    assigned_by   TEXT NOT NULL,
    quiz_answers  TEXT,
    assigned_at   TEXT,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS archetype_monthly_stat (
    month         TEXT NOT NULL,
    archetype_id  TEXT NOT NULL,
    user_count    INTEGER NOT NULL,
    denominator   INTEGER NOT NULL,
    computed_at   TEXT,
    PRIMARY KEY (month, archetype_id)
);
