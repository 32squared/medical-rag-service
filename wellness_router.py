"""wellness_router.py — 웰니스 코칭 라우터 + 핸드오프 트리거 (P1, 룰 기반·순수 함수).

정본: docs/plan/18-wellness-coaching.md §2-A(라우터) · §3-A(핸드오프 트리거).
- 결정적(키워드 사전 + intent + 밴드) — LLM 추가호출 0.
- `WELLNESS_ROUTER_ENABLED`(기본 off) 게이트는 호출 측(rag_engine)에서 적용. 본 모듈 함수는 순수.
- 안전: 응급(intent=emergency)이면 코칭 버튼 차단 + referral=emergency(I7·WC-C4 상속).
- P1 범위: 의료 답변에 '실천 코칭' 버튼 노출 여부만 결정. 실제 코칭 KB·플랜 생성은 P2.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

# ── 트랙 키워드 사전 (§2-A.1 도메인 키워드 / §3-A actionable 판정) ──────────────
TRACK_KEYWORDS: Dict[str, tuple] = {
    "diet": ("식단", "식이", "저염", "나트륨", "음식", "먹", "식사", "외식", "채소",
             "영양", "칼로리", "당분", "다이어트", "체중", "살 빼", "비만"),
    "exercise": ("운동", "걷기", "산책", "헬스", "유산소", "근력", "스트레칭",
                 "활동량", "걸음", "조깅", "등산", "요가", "체력"),
    "habit": ("수면", "잠", "불면", "스트레스", "금연", "담배", "흡연", "절주",
              "음주", "생활습관", "휴식"),
}

# 순수 정보 신호(실천 여지 낮음) — 정의·성분·수치 해석만 묻는 질의 (§3-A.3 pure_info)
_PURE_INFO_HINTS = ("성분", "정의", "뜻", "무엇", "뭐야", "원리", "부작용", "수치")

_BAND_RANK = {"안정": 0, "주의": 1, "경고": 2}


def is_enabled() -> bool:
    """WELLNESS_ROUTER_ENABLED 플래그 (기본 off → P1 미적용 시 기존 행동 무변화)."""
    return os.environ.get("WELLNESS_ROUTER_ENABLED", "false").lower() in (
        "1", "true", "yes", "on")


def detect_topic(text: str) -> Optional[str]:
    """텍스트에서 코칭 트랙(diet/exercise/habit) 감지. 없으면 None. 첫 매치 우선순위=식단>운동>습관."""
    if not text:
        return None
    for track in ("diet", "exercise", "habit"):
        for kw in TRACK_KEYWORDS[track]:
            if kw in text:
                return track
    return None


def worst_band(labels: List[Optional[str]]) -> Optional[str]:
    """밴드 라벨 리스트에서 가장 보수적인 값(경고>주의>안정). 없으면 None."""
    ranked = [(l, _BAND_RANK[l]) for l in labels if l in _BAND_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda x: x[1])[0]


def classify_domain(query: str, intent: Optional[str] = None,
                    mode: str = "medical") -> str:
    """§2-A.1 라우팅 — 'medical' | 'wellness'. 우선순위 순(위가 이김), fail-closed=medical.

    P1에선 RAG가 모든 질의를 처리하므로 advisory(핸드오프가 실제 진입). 향후 라우팅에 사용.
    """
    if intent == "emergency":                 # 1. 응급 → medical 우회(I7)
        return "medical"
    if isinstance(mode, str) and mode.startswith("wellness"):  # 2. 코칭 모드 유지
        return "wellness"
    if intent in ("diagnosis", "drug", "symptom", "medication"):  # 4. 의학 intent
        return "medical"
    if detect_topic(query):                    # 5. 도메인 키워드 → wellness 후보
        return "wellness"
    return "medical"                           # 6. 기본값(보수적)


def detect_handoff(query: str, answer: str, intent: Optional[str] = None,
                   band: Optional[str] = None, mode: str = "medical") -> Dict:
    """§3-A.3 '실천 여지 감지' 훅 — 코칭 버튼·referral 노출 결정(결정적).

    Returns dict:
      show (bool)        코칭 버튼 노출
      topic (str|None)   diet/exercise/habit
      copy ('full'|'soft'|None) · label(한국어)
      banner (bool)      진료 병행 배너(주의/경고)
      referral ('emergency'|'hospital'|None)
      reason (str|None)  미노출 사유(감사)
    """
    topic = detect_topic(f"{query or ''} {answer or ''}")

    def _r(show, copy=None, label=None, banner=False, referral=None, reason=None):
        return {"show": show, "topic": topic, "copy": copy, "label": label,
                "banner": banner, "referral": referral, "reason": reason}

    # 1. 응급 — 코칭 차단 + 응급 referral (I7·WC-C4)
    if intent == "emergency" or band == "응급":
        return _r(False, referral="emergency", reason="emergency")
    # 6. 코칭 모드면 버튼 대신 모드 내 후속 (P1 mode=medical이라 보통 미해당)
    if isinstance(mode, str) and mode.startswith("wellness"):
        return _r(False, reason="coaching_mode")
    # 5. 순수 정보질의 / 실천 여지 없음 → 미노출(fail-closed, 옵트인이라 손해 없음)
    if topic is None:
        return _r(False, reason="not_actionable")
    if _is_pure_info(query):
        return _r(False, reason="pure_info")
    # 2~4. actionable & 비응급 — 밴드별 문구
    if band == "경고":
        return _r(True, copy="soft", label="진료와 병행할 가벼운 생활수칙",
                  banner=True, referral="hospital")
    if band == "주의":
        return _r(True, copy="full", label="실천 코칭 받기", banner=True)
    return _r(True, copy="full", label="실천 코칭 받기")   # 안정/None


def _is_pure_info(query: str) -> bool:
    """정의·성분·수치 해석만 묻는 질의(행동 함의 없음) 추정. 트랙 키워드가 있어도 정보질의면 억제."""
    if not query:
        return False
    return any(h in query for h in _PURE_INFO_HINTS)
