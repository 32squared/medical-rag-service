"""context_feeds 순수 함수 단위 테스트 — 네트워크 불필요."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context_feeds import (
    fetch_air_quality,
    grade_pm10,
    grade_pm25,
    render_context_for_prompt,
    summarize_air_quality,
)


def test_grade_pm25_cai_boundaries():
    """환경부 CAI 등급 경계값 (vital_reference_ranges와 동일 기준)."""
    assert grade_pm25(0) == "좋음"
    assert grade_pm25(15) == "좋음"
    assert grade_pm25(16) == "보통"
    assert grade_pm25(35) == "보통"
    assert grade_pm25(36) == "나쁨"
    assert grade_pm25(75) == "나쁨"
    assert grade_pm25(76) == "매우나쁨"
    assert grade_pm25(None) == "정보없음"


def test_grade_pm10_cai_boundaries():
    assert grade_pm10(30) == "좋음"
    assert grade_pm10(31) == "보통"
    assert grade_pm10(80) == "보통"
    assert grade_pm10(81) == "나쁨"
    assert grade_pm10(151) == "매우나쁨"


def test_summarize_air_quality_averages():
    items = [
        {"pm25Value": "30", "pm10Value": "50"},
        {"pm25Value": "50", "pm10Value": "70"},
        {"pm25Value": "-", "pm10Value": ""},      # 결측 측정소 무시
        {"pm25Value": "abc"},                       # 파싱 불가 무시
    ]
    s = summarize_air_quality(items, sido="서울")
    assert s["pm25_avg"] == 40.0
    assert s["pm25_grade"] == "나쁨"
    assert s["pm10_avg"] == 60.0
    assert s["pm10_grade"] == "보통"
    assert s["sido"] == "서울"
    assert "에어코리아" in s["source"]


def test_summarize_empty_returns_none():
    assert summarize_air_quality([]) is None
    assert summarize_air_quality([{"pm25Value": "-"}]) is None


def test_fetch_without_key_returns_none(monkeypatch):
    """키 미설정 시 무해 폴백 (네트워크 호출 없음)."""
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    assert fetch_air_quality(sido="서울", api_key="") is None


def test_render_context_for_prompt():
    feeds = {"air_quality": {
        "sido": "서울", "pm25_avg": 40.0, "pm25_grade": "나쁨",
        "pm10_avg": 60.0, "pm10_grade": "보통",
        "source": "에어코리아(환경부) 실시간 측정 / CAI 등급 기준",
    }}
    text = render_context_for_prompt(feeds)
    assert "나쁨" in text and "출처" in text


def test_render_empty_feeds():
    assert render_context_for_prompt({}) == ""
    assert render_context_for_prompt({"air_quality": None}) == ""
