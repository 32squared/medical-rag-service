-- 025 — 루틴 팩 플랫폼. 정본 docs/plan/28-routine-pack-platform.md FR-S4.
-- 프로그램이 시작 시점의 팩(id·버전)을 기억한다. 기존 행은 기본값 = 건강 12주 팩 v1.
-- weeks_total 컬럼은 023 에 이미 있다(기본 12). 재적용 안전(IF NOT EXISTS).

ALTER TABLE routine_program ADD COLUMN IF NOT EXISTS pack_id TEXT DEFAULT 'health_12w';

ALTER TABLE routine_program ADD COLUMN IF NOT EXISTS pack_version INTEGER DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_routine_program_pack ON routine_program (pack_id);
