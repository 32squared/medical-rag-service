-- 019_analytics_coaching_dims.sql — analytics_events에 웰니스 코칭 비식별 차원 추가 (18 §7)
-- track(트랙 라벨 diet/exercise/habit) · checkin_done(일일 실천 bool) · streak(연속일 count).
-- 전부 비식별(라벨/불리언/카운트) — 원시값/진단명/원문 미저장 원칙 유지. band는 기존 risk_level 재사용.
ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS track TEXT;
ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS checkin_done INTEGER;
ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS streak INTEGER;
