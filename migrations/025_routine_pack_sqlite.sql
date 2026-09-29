-- 025 — 루틴 팩 플랫폼(SQLite). 정본 docs/plan/28-routine-pack-platform.md FR-S4.
-- SQLite 는 ADD COLUMN IF NOT EXISTS 가 없다. 러너가 문장별 try/except 하므로 재적용 시 실패는 무시된다.

ALTER TABLE routine_program ADD COLUMN pack_id TEXT DEFAULT 'health_12w';

ALTER TABLE routine_program ADD COLUMN pack_version INTEGER DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_routine_program_pack ON routine_program (pack_id);
