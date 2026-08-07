-- (SQLite 판 — DDL 은 PG 와 동일 문법으로 작성되어 그대로 사용)
-- 023 — 루틴형 전환(12주 프로그램) 영속 테이블. 정본 docs/plan/25-routine-transition-spec.md E-2.
-- 저장 금지 원칙: 원시 측정값/진단명 미저장. value 는 선택지 라벨만(비슷/높음/낮음, 시각, 태그).
-- 러너가 세미콜론으로 분리해 각 문을 try/except 하므로 재적용 안전. 주석에 세미콜론 리터럴 금지.

CREATE TABLE IF NOT EXISTS routine_program (
    program_id          TEXT PRIMARY KEY,
    subject_id          TEXT NOT NULL,
    plan_id             TEXT,
    track               TEXT NOT NULL,
    focus               TEXT,
    anchor              TEXT,
    intake_json         TEXT,
    band_at_start       TEXT,
    item_cap            INTEGER DEFAULT 0,
    started_on          TEXT NOT NULL,
    current_week        INTEGER DEFAULT 1,
    weeks_total         INTEGER DEFAULT 12,
    status              TEXT DEFAULT 'active',
    mode                TEXT DEFAULT 'daily',
    adherence_state     TEXT DEFAULT 'active',
    paused_days         INTEGER DEFAULT 0,
    paused_until        TEXT,
    freeze_used_on      TEXT,
    week_state_json     TEXT,
    nudge_sent_json     TEXT,
    curriculum_version  INTEGER DEFAULT 1,
    last_seen_on        TEXT,
    completed_on        TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

CREATE INDEX IF NOT EXISTS ix_routine_program_subject ON routine_program (subject_id, status);

CREATE TABLE IF NOT EXISTS routine_checkin (
    checkin_id      TEXT PRIMARY KEY,
    program_id      TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    action_date     TEXT NOT NULL,
    week_no         INTEGER,
    slot            TEXT NOT NULL,
    item_key        TEXT NOT NULL,
    status          TEXT NOT NULL,
    value           TEXT,
    barrier         TEXT,
    undo_count      INTEGER DEFAULT 0,
    idempotency_key TEXT,
    client_ts       TEXT,
    created_at      TEXT,
    updated_at      TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_routine_checkin_day ON routine_checkin (program_id, action_date, item_key);

CREATE UNIQUE INDEX IF NOT EXISTS ux_routine_checkin_idem ON routine_checkin (idempotency_key);

CREATE INDEX IF NOT EXISTS ix_routine_checkin_subject_date ON routine_checkin (subject_id, action_date);

CREATE TABLE IF NOT EXISTS routine_report (
    program_id    TEXT NOT NULL,
    week_no       INTEGER NOT NULL,
    done_days     INTEGER,
    goal_days     INTEGER,
    adherence     INTEGER,
    streak_end    INTEGER,
    na_days       INTEGER,
    badges_json   TEXT,
    transition    TEXT,
    generated_at  TEXT,
    read_at       TEXT,
    PRIMARY KEY (program_id, week_no)
);

CREATE TABLE IF NOT EXISTS routine_notify_pref (
    subject_id   TEXT PRIMARY KEY,
    hhmm         TEXT,
    channel      TEXT,
    push_granted INTEGER DEFAULT 0,
    updated_at   TEXT
);
