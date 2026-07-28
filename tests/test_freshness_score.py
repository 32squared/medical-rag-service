"""
신선도 점수 테스트 (04-kb-expansion-list.md 메타데이터 §1).

_weighted_rerank의 freshness 인자(10%) 로직. 날짜 미색인 문서는 중립(0.5)이라
기존 동작과 동일(무회귀)하고, 날짜가 있으면 최신성을 반영한다.
"""

from datetime import date

from rag_engine import _freshness_score

_TODAY = date(2026, 6, 20)  # 결정적 기준일


def test_missing_date_is_neutral():
    """날짜 미색인 → 0.5(중립, 무회귀)."""
    assert _freshness_score(None, today=_TODAY) == 0.5
    assert _freshness_score("", today=_TODAY) == 0.5
    assert _freshness_score("not-a-date", today=_TODAY) == 0.5


def test_recent_is_high():
    """최근 1년 이내 → 1.0."""
    assert _freshness_score("2026-01-01", today=_TODAY) == 1.0
    assert _freshness_score("2025-09-01", today=_TODAY) == 1.0


def test_old_is_low():
    """6년 이상 경과 → 0.3 바닥."""
    assert _freshness_score("2018-01-01", today=_TODAY) == 0.3
    assert _freshness_score("2010-05-05", today=_TODAY) == 0.3


def test_mid_age_decays_monotonically():
    """1~6년 구간은 단조 감소."""
    s2 = _freshness_score("2024-06-20", today=_TODAY)   # ~2년
    s4 = _freshness_score("2022-06-20", today=_TODAY)   # ~4년
    assert 0.3 < s4 < s2 < 1.0


def test_future_date_neutral():
    """미래 날짜(데이터 오류) → 중립."""
    assert _freshness_score("2030-01-01", today=_TODAY) == 0.5


def test_iso_datetime_string_parsed():
    """'YYYY-MM-DDTHH:MM:SSZ' 형식도 앞 10자로 파싱."""
    assert _freshness_score("2026-01-01T12:00:00Z", today=_TODAY) == 1.0
