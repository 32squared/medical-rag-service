-- =============================================================================
-- 010_vital_reference_ranges.sql — 생체신호·환경 공인 참조범위 구조화 테이블 (PostgreSQL)
-- KB 확장 P2: LLM이 기준값을 생성하지 못하게 하는 환각 방어의 핵심.
-- 답변은 이 테이블 lookup 결과(또는 이를 원문으로 적재한 KB 문서)만 인용한다.
-- 멱등성: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS
-- 시드 데이터: seed_reference_ranges.py (코드 — 출처·버전 명기 의무)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vital_reference_ranges (
    id              TEXT PRIMARY KEY,       -- 'bp.adult.kr.ksh2022' 형식
    signal_key      TEXT NOT NULL,          -- 'blood_pressure'|'fasting_glucose'|'spo2'|
                                            -- 'body_temperature'|'pm25'|'co2_indoor'|'bmi'...
    population      TEXT NOT NULL DEFAULT 'adult',
                                            -- 'adult'|'child'|'infant_lt3m'|'pregnant'|'elderly'|'all'
    locale          TEXT NOT NULL DEFAULT 'KR',   -- 'KR'|'US'|'GLOBAL' (로케일별 기준 상이)
    unit            TEXT NOT NULL,          -- UCUM ('mm[Hg]','mg/dL','%','Cel','ug/m3','[ppm]')
    ranges_json     TEXT NOT NULL,          -- JSON [{label, min, max, note}] — 구간 정의
    source_name     TEXT NOT NULL,          -- '대한고혈압학회 2022 진료지침' 등 공식 출처
    source_url      TEXT,
    source_version  TEXT,                   -- 'KSH 2022' | 'WHO AQG 2021' ...
    effective_date  TEXT,                   -- 지침 발효/발행일 (감사·재현 요건)
    notes           TEXT,                   -- 측정 조건·오차 요인 등 부가 설명
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vital_ref_signal
    ON vital_reference_ranges(signal_key, locale, population);
