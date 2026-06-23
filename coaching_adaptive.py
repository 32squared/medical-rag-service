"""coaching_adaptive.py — 적응형 지속 루프(§4-B): 실천 신호 → 다음 코칭 액션·무비난 메시지.

정본: docs/plan/18-wellness-coaching.md §4-B(지속 루프)·§4-B.5(무비난 재참여).
순수 함수 — 입력은 게이미피케이션 집계(실천율·스트릭·이탈일·완주). DB·LLM 불필요.

컴플라이언스(WC-C): 메시지는 **행동(실천 지속)만** 다룬다 — 건강 결과·효능·진단을 표방하지
않는다(예: "혈압이 좋아져요" 금지). 이탈 시 죄책감 유발 없이(다크패턴 거부, §4-B.10) 재초대만.
경고/응급 밴드의 강한 톤완화는 호출 측(coaching_engine/router)에서 이미 처리 — 여기선 행동 톤만.
"""
from __future__ import annotations

from typing import Dict

# 액션 → 무비난·행동전용 메시지(건강결과 비표방). {streak}만 보간.
_MESSAGES = {
    "celebrate":        "첫 완주예요! 꾸준함이 정말 멋져요 🎉 다음 챌린지로 이어가볼까요?",
    "advance":          "🔥 {streak}일 연속! 흐름이 좋아요. 한 단계 올려볼 준비가 됐어요.",
    "encourage":        "오늘도 한 걸음. 작은 실천이 차곡차곡 쌓이고 있어요.",
    "simplify":         "요즘 바쁘셨죠? 부담을 줄여 더 쉬운 목표로 다시 잡아드릴게요.",
    "reengage_gentle":  "잠깐 쉬어가도 괜찮아요. 오늘 딱 한 가지만 다시 시작해봐요.",
    "reengage_replan":  "며칠 비었네요 — 편하게 계획을 새로 잡아드릴게요. 죄책감은 내려놓으세요.",
    "dormant":          "언제든 돌아오시면 반갑게 맞이할게요. 작은 것부터 다시 함께해요.",
}


def next_action(adherence: int, streak: int, days_since_last: int = 1,
                completed: bool = False) -> str:
    """실천 신호 → 다음 코칭 액션(결정적 우선순위). 이탈(공백)이 성취보다 우선."""
    if completed:
        return "celebrate"
    if days_since_last >= 8:
        return "dormant"
    if days_since_last >= 4:
        return "reengage_replan"
    if days_since_last >= 2:
        return "reengage_gentle"
    if streak >= 7 and adherence >= 80:
        return "advance"
    if adherence < 40:
        return "simplify"
    return "encourage"


def message(action: str, streak: int = 0) -> str:
    return _MESSAGES.get(action, _MESSAGES["encourage"]).format(streak=streak)


def coach(adherence: int, streak: int, days_since_last: int = 1,
          completed: bool = False) -> Dict:
    """게이미피케이션 신호 → {action, message, no_blame, reengage}. 항상 무비난."""
    a = next_action(adherence, streak, days_since_last, completed)
    return {
        "action": a,
        "message": message(a, streak),
        "no_blame": True,
        "reengage": a.startswith("reengage") or a == "dormant",
    }
