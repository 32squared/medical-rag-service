"""test_coaching_gamification.py — 지속 루프(스트릭·포인트·배지·재참여) 순수 테스트 (P4)."""
import coaching_gamification as g


def test_current_streak():
    assert g.current_streak([True, False, True, True, True]) == 3
    assert g.current_streak([True, True, False]) == 0
    assert g.current_streak([]) == 0
    assert g.current_streak([True] * 5) == 5


def test_best_streak():
    assert g.best_streak([True, True, False, True, True, True]) == 3
    assert g.best_streak([False, False]) == 0


def test_points_with_streak_bonus():
    assert g.points(5, 0) == 50
    assert g.points(5, 3) == 70       # +20 (3일)
    assert g.points(5, 7) == 100      # +50 (7일)


def test_level_thresholds():
    assert g.level(0) == 1
    assert g.level(120) == 2
    assert g.level(1000) == 5


def test_badges_behavior_based():
    assert g.badges(0) == []
    assert "입문" in g.badges(1)
    assert "작심삼일 격파" in g.badges(3)
    assert "일주일" in g.badges(7)
    assert "첫 완주" in g.badges(7, completed_challenge=True)


def test_adherence_and_completion():
    assert g.adherence_rate(10, 14) == 71
    assert g.is_completed(10, 14) is True     # 71% ≥ 70
    assert g.is_completed(9, 14) is False     # 64%
    assert g.adherence_rate(0, 0) == 0


def test_reengage_states():
    assert g.reengage_state(1) == "none"
    assert g.reengage_state(3) == "gentle"
    assert g.reengage_state(7) == "replan"
    assert g.reengage_state(14) == "dormant"


def test_summary():
    s = g.summary([True, True, True, False, True, True], plan_days=14)
    assert s["done"] == 5
    assert s["streak"] == 2 and s["best_streak"] == 3
    assert s["level"] >= 1 and "작심삼일 격파" in s["badges"]
    assert s["completed"] is False
