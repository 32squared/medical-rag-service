"""test_wellness_router.py — 웰니스 라우터·핸드오프 트리거 (P1, 순수 함수).

정본: docs/plan/18-wellness-coaching.md §2-A(라우터) · §3-A.2(노출 결정표).
결정적이라 LLM/DB 불필요 — 순수 단위 테스트.
"""
import os
import wellness_router as wr


# ── detect_topic ──────────────────────────────────────────────
def test_detect_topic_tracks():
    assert wr.detect_topic("저염 식단 알려줘") == "diet"
    assert wr.detect_topic("걷기 운동 어떻게") == "exercise"
    assert wr.detect_topic("요즘 잠을 못 자요") == "habit"
    assert wr.detect_topic("오늘 날씨 어때") is None
    assert wr.detect_topic("") is None


def test_detect_topic_priority_diet_first():
    # 식단·운동 키워드 동시 → 식단 우선(우선순위 순회)
    assert wr.detect_topic("식단이랑 운동 둘 다") == "diet"


# ── worst_band ────────────────────────────────────────────────
def test_worst_band():
    assert wr.worst_band(["안정", "경고", "주의"]) == "경고"
    assert wr.worst_band(["안정", "주의"]) == "주의"
    assert wr.worst_band(["안정"]) == "안정"
    assert wr.worst_band([]) is None
    assert wr.worst_band([None, "잡값"]) is None


# ── classify_domain (§2-A.1) ──────────────────────────────────
def test_classify_domain():
    assert wr.classify_domain("숨을 못 쉬어요", intent="emergency") == "medical"
    assert wr.classify_domain("외식 줄이는 법", mode="wellness:diet") == "wellness"
    assert wr.classify_domain("이 약 부작용?", intent="drug") == "medical"
    assert wr.classify_domain("저염 식단 추천") == "wellness"
    assert wr.classify_domain("혈압이 뭐예요") == "medical"   # 트랙 키워드 없음 → 기본 medical


# ── detect_handoff (§3-A.2 결정표) ────────────────────────────
def test_handoff_emergency_blocks_button():
    h = wr.detect_handoff("숨을 못 쉬어요", "119에 연락하세요", intent="emergency")
    assert h["show"] is False
    assert h["referral"] == "emergency"
    assert h["reason"] == "emergency"


def test_handoff_warning_band_soft():
    h = wr.detect_handoff("혈압 낮추려면 식단?", "저염이 도움됩니다", band="경고")
    assert h["show"] is True
    assert h["copy"] == "soft"
    assert h["banner"] is True
    assert h["referral"] == "hospital"


def test_handoff_caution_band_full_with_banner():
    h = wr.detect_handoff("저염 식단 알려줘", "채소를 늘리세요", band="주의")
    assert h["show"] is True
    assert h["copy"] == "full"
    assert h["banner"] is True


def test_handoff_stable_band_full_no_banner():
    h = wr.detect_handoff("운동 어떻게 시작?", "걷기부터 해보세요", band="안정")
    assert h["show"] is True
    assert h["copy"] == "full"
    assert h["banner"] is False


def test_handoff_no_band_full():
    h = wr.detect_handoff("식단 관리 팁", "균형 잡힌 식사를", band=None)
    assert h["show"] is True
    assert h["topic"] == "diet"


def test_handoff_topic_from_answer():
    # 질의엔 트랙 키워드 없어도 답변에 있으면 actionable
    h = wr.detect_handoff("혈압이 높게 나왔어요", "저염 식단이 도움이 됩니다", band="주의")
    assert h["show"] is True
    assert h["topic"] == "diet"


def test_handoff_not_actionable_suppressed():
    h = wr.detect_handoff("이 약 성분이 뭐야", "아세트아미노펜입니다")
    assert h["show"] is False
    assert h["reason"] == "not_actionable"


def test_handoff_pure_info_suppressed():
    # 트랙 키워드(식단) 있어도 정의·성분 질의면 억제
    h = wr.detect_handoff("저염 식단의 정의가 뭐야", "")
    assert h["show"] is False
    assert h["reason"] == "pure_info"


def test_handoff_coaching_mode_suppressed():
    h = wr.detect_handoff("외식 줄이는 법", "국물을 남겨보세요", mode="wellness:diet")
    assert h["show"] is False
    assert h["reason"] == "coaching_mode"


# ── is_enabled 플래그 ─────────────────────────────────────────
def test_is_enabled_default_off(monkeypatch):
    monkeypatch.delenv("WELLNESS_ROUTER_ENABLED", raising=False)
    assert wr.is_enabled() is False
    monkeypatch.setenv("WELLNESS_ROUTER_ENABLED", "on")
    assert wr.is_enabled() is True
    monkeypatch.setenv("WELLNESS_ROUTER_ENABLED", "false")
    assert wr.is_enabled() is False
