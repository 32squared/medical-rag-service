"""
수집 건전성 평가 테스트 (07-revised-plan.md §4-4).
"""

from collection_health import assess_collection_health


def test_all_ok():
    r = assess_collection_health({"kdca_api": 50, "nemc": 18})
    assert r["healthy"] is True
    assert r["warnings"] == []
    assert set(r["status"].values()) == {"ok"}


def test_empty_source_flagged():
    """0건 출처는 empty 경고(MFDS NAT IP 차단 시나리오)."""
    r = assess_collection_health({"kdca_api": 50, "mfds": 0})
    assert r["healthy"] is False
    assert r["status"]["mfds"] == "empty"
    assert any("mfds" in w for w in r["warnings"])


def test_expected_but_missing_is_empty():
    """기대했으나 counts에 없는 출처도 empty."""
    r = assess_collection_health({"kdca_api": 50}, expected_sources=["kdca_api", "nemc"])
    assert r["status"]["nemc"] == "empty"
    assert r["healthy"] is False


def test_sharp_drop_flagged_low():
    """baseline 대비 절반 미만으로 급감하면 low(스크래핑 손상 의심)."""
    r = assess_collection_health(
        {"health_kdca": 20}, baseline={"health_kdca": 200}, drop_threshold=0.5
    )
    assert r["status"]["health_kdca"] == "low"
    assert r["healthy"] is False
    assert any("급감" in w for w in r["warnings"])


def test_mild_drop_within_threshold_ok():
    """임계 이상이면 정상(노이즈 억제)."""
    r = assess_collection_health(
        {"health_kdca": 150}, baseline={"health_kdca": 200}, drop_threshold=0.5
    )
    assert r["status"]["health_kdca"] == "ok"
    assert r["healthy"] is True


def test_empty_counts_is_healthy():
    """평가 대상이 없으면 healthy=True(빈 실행)."""
    assert assess_collection_health({})["healthy"] is True
