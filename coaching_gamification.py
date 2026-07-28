"""coaching_gamification.py — 지속 루프(스트릭·포인트·배지·레벨·재참여) (P4, 순수 함수).

정본: docs/plan/18-wellness-coaching.md §4-B(지속 루프)·§4-B.9(게이미피케이션 스펙).
체크인 기록(일별 done bool)에서 결정적 계산 — DB·LLM 불필요.
듀오링고 벤치마크(§4-B.10) 차용하되 **목적함수는 비차용**: 보상은 실천(행동)에만 연동,
건강 결과(밴드)엔 비연동. 경고밴드 톤완화는 호출 측 UI에서.
"""
from __future__ import annotations

from typing import Dict, List

# 포인트(§4-B.9): 체크인 +10 · 3일 +20 · 7일 +50 (스트릭 보너스, 누적 아님 — 현재 스트릭 기준)
_PT_CHECKIN = 10
_LEVELS = [(0, 1), (100, 2), (250, 3), (500, 4), (1000, 5)]   # 누적 포인트 → 레벨


def current_streak(daily_done: List[bool]) -> int:
    """가장 최근(끝)에서 연속된 실천 일수(트레일링 연속 True)."""
    s = 0
    for d in reversed(daily_done or []):
        if d:
            s += 1
        else:
            break
    return s


def best_streak(daily_done: List[bool]) -> int:
    """기간 내 최장 연속 실천 일수."""
    best = cur = 0
    for d in (daily_done or []):
        cur = cur + 1 if d else 0
        best = max(best, cur)
    return best


def points(done_count: int, streak: int) -> int:
    """누적 포인트 — 체크인×10 + 현재 스트릭 보너스(3일 +20 / 7일 +50)."""
    p = max(0, int(done_count)) * _PT_CHECKIN
    if streak >= 7:
        p += 50
    elif streak >= 3:
        p += 20
    return p


def level(points_val: int) -> int:
    lv = 1
    for thr, l in _LEVELS:
        if points_val >= thr:
            lv = l
    return lv


def badges(best: int, completed_challenge: bool = False) -> List[str]:
    """획득 배지(행동 기반 — 건강결과 비연동)."""
    b: List[str] = []
    if best >= 1:
        b.append("입문")
    if best >= 3:
        b.append("작심삼일 격파")
    if best >= 7:
        b.append("일주일")
    if completed_challenge:
        b.append("첫 완주")
    return b


def adherence_rate(done_count: int, plan_days: int) -> int:
    """실천율(%) — 완주 판정 기준(§4-B.9: 70%+)."""
    if not plan_days:
        return 0
    return round(max(0, done_count) / plan_days * 100)


def is_completed(done_count: int, plan_days: int, threshold: int = 70) -> bool:
    """챌린지 완주 판정(실천율 ≥ threshold%)."""
    return adherence_rate(done_count, plan_days) >= threshold


def reengage_state(days_since_last: int) -> str:
    """이탈·재참여(§4-B.5, 무비난). 1=none · ~3=gentle · ~7=replan · 그 이상=dormant."""
    if days_since_last <= 1:
        return "none"
    if days_since_last <= 3:
        return "gentle"
    if days_since_last <= 7:
        return "replan"
    return "dormant"


def summary(daily_done: List[bool], plan_days: int, completed: bool = False) -> Dict:
    """체크인 일별 done → 지속 루프 요약(홈·진척 카드용)."""
    done = sum(1 for d in (daily_done or []) if d)
    cur = current_streak(daily_done)
    best = best_streak(daily_done)
    pts = points(done, cur)
    comp = completed or is_completed(done, plan_days)
    return {
        "done": done,
        "streak": cur,
        "best_streak": best,
        "points": pts,
        "level": level(pts),
        "badges": badges(best, comp),
        "adherence": adherence_rate(done, plan_days),
        "completed": comp,
    }
