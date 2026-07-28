"""test_facility_finder.py — 가까운 시설 찾기(거리·영업시간·영업중) 순수 테스트 (§5.8)."""
from datetime import datetime
import facility_finder as ff


def test_open_now_weekday_hours():
    fac = {"open": "09:00", "close": "18:00", "days": "평일"}
    assert ff.open_now(fac, datetime(2026, 6, 24, 10, 0)) is True    # 수 10시
    assert ff.open_now(fac, datetime(2026, 6, 24, 19, 0)) is False   # 마감 후
    assert ff.open_now(fac, datetime(2026, 6, 27, 10, 0)) is False   # 토요일


def test_open_now_24h():
    fac = {"open": "00:00", "close": "24:00", "days": "매일"}
    assert ff.open_now(fac, datetime(2026, 6, 24, 3, 0)) is True
    assert ff.open_now(fac, datetime(2026, 6, 28, 23, 30)) is True   # 일요일 심야


def test_find_sorts_open_first_then_distance():
    res = ff.find("pharmacy", datetime(2026, 6, 24, 23, 0))   # 수 23시 — 24시 약국만 영업
    assert res[0]["open_now"] is True
    assert res[0]["name"] == "24시명문약국"      # 영업중 우선
    # 영업중 끼리는 거리순
    opens = [r for r in res if r["open_now"]]
    assert opens == sorted(opens, key=lambda x: x["dist_m"])


def test_find_enriches_fields():
    r = ff.find("hospital", datetime(2026, 6, 24, 10, 0))[0]
    assert "dist_label" in r and "hours" in r and r["map_url"].startswith("http")
    assert r["tel_url"].startswith("tel:")


def test_dist_label():
    assert ff._dist_label(280) == "280m"
    assert ff._dist_label(1200) == "1.2km"


def test_find_demo_wrapper():
    out = ff.find_demo("pharmacy", region="역삼동")
    assert out["demo"] is True and out["items"] and "공공 API" in out["notice"]
