-- 022_analytics_consent_dim.sql — analytics_events 에 동의 비식별 차원 추가 (23 §2)
-- consent_item(동의 항목 키 라벨 personal_info 등). 비식별 라벨만 — 원시값/식별자 미저장.
ALTER TABLE analytics_events ADD COLUMN IF NOT EXISTS consent_item TEXT;
