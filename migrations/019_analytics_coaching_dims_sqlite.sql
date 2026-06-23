-- 019 sqlite — analytics_events 코칭 비식별 차원(track·checkin_done·streak).
-- 러너가 세미콜론으로 분리하고 각 문을 try/except 하므로 중복 컬럼(재적용)은 무시된다. 주석에 세미콜론 리터럴 금지.
ALTER TABLE analytics_events ADD COLUMN track TEXT;
ALTER TABLE analytics_events ADD COLUMN checkin_done INTEGER;
ALTER TABLE analytics_events ADD COLUMN streak INTEGER;
