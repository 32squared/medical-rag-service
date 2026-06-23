"""anticipatory_engine.py — 선제(Anticipatory) 트리거 엔진 (순수 함수).

정본: docs/plan/21-gap-analysis.md §5.1(G1) · docs/plan/20 §2.2(Anticipatory Canvas).
"AI가 무엇을·언제·어떻게 **안전하게** 표면화하는가" — 결정적 규칙(LLM 아님).
- 입력은 비식별 라벨/카운트/bool (밴드·추세·복약·검진·코칭). 원시값·진단명 미사용(I1/I12).
- 안전: 응급 최우선(I7) · 불확실하면 미표면화 · 중립 언어 · "진단 아님" 병기.
- 한 번에 must-attend 1개(과부하 금지). 빈도 캡은 호출 측(surfacing_event)에서.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def _s(rule, priority, kind, text, **extra) -> Dict:
    d = {"rule": rule, "priority": priority, "kind": kind, "text": text}
    d.update(extra)
    return d


def evaluate(signals: Dict) -> List[Dict]:
    """비식별 신호 → 우선순위 정렬된 표면화 후보 리스트.

    signals(전부 라벨/카운트/bool):
      emergency(bool) · band('안정'|'주의'|'경고'|'응급') · warning_days(int)
      trend('악화'|'개선'|'유지') · med_due(bool) · checkup_d(int|None)
      coaching_missed_days(int)
    """
    out: List[Dict] = []
    band = signals.get("band")
    wd = int(signals.get("warning_days") or 0)

    # R0 응급 — 최우선(I7), 모든 것 위로
    if signals.get("emergency") or band == "응급":
        out.append(_s("R0", 0, "emergency", "지금 119·응급실로 바로 연락하세요", referral="emergency"))

    # R1 경고/주의 밴드 연속 — must-attend(진료 고려)
    if band == "경고" and wd >= 1:
        out.append(_s("R1", 1, "must_attend",
                      "혈압이 며칠째 경고 구간이에요. 이번 주 안에 진료를 고려해보세요",
                      referral="hospital", note="측정 구간 기준 · 진단은 아니에요"))
    elif band == "주의" and wd >= 3:
        out.append(_s("R1b", 1, "must_attend",
                      "혈압 주의 구간이 며칠째 이어져요. 재측정과 생활관리를 권해요",
                      note="측정 구간 기준 · 진단은 아니에요"))

    # R2 복약·검진 임박
    if signals.get("med_due"):
        out.append(_s("R2", 2, "reminder", "복약 시간이에요"))
    cd = signals.get("checkup_d")
    if cd is not None and int(cd) <= 7:
        out.append(_s("R2c", 2, "reminder", f"건강검진이 {int(cd)}일 남았어요"))

    # R3 추세 악화(주의 동반)
    if signals.get("trend") == "악화" and band == "주의":
        out.append(_s("R3", 3, "info", "최근 흐름이 조금 올라가는 편이에요"))

    # R4 코칭 재참여(무비난)
    if int(signals.get("coaching_missed_days") or 0) >= 3:
        out.append(_s("R4", 4, "nudge", "오늘 1탭이면 실천이 이어져요"))

    out.sort(key=lambda x: x["priority"])
    return out


def top(signals: Dict) -> Optional[Dict]:
    """지금 표면화할 단 하나(must-attend 1개 원칙). 없으면 None(=조용)."""
    cands = evaluate(signals)
    return cands[0] if cands else None


def anticipated_questions(signals: Dict) -> List[str]:
    """'궁금하실 거예요' — 맥락 기반 예상 질문(화이트리스트, 결정적)."""
    qs: List[str] = []
    band = signals.get("band")
    if band in ("주의", "경고"):
        qs.append("어제는 왜 더 높았을까요?")
        qs.append("저염 말고 또 뭐가 도움될까요?")
    if signals.get("trend") == "악화":
        qs.append("이 흐름을 어떻게 되돌릴 수 있을까요?")
    return qs[:3]


def should_surface(signals: Dict, dismissed_rules: Optional[List[str]] = None) -> Optional[Dict]:
    """빈도 캡·피로 관리 반영 — 사용자가 무시한 규칙은 제외(응급은 예외=항상)."""
    dismissed = set(dismissed_rules or [])
    for c in evaluate(signals):
        if c["rule"] == "R0":          # 응급은 무시 불가
            return c
        if c["rule"] not in dismissed:
            return c
    return None
