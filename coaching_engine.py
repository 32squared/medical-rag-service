"""coaching_engine.py — 웰니스 코칭 엔진 (P2, 식단 트랙 MVP).

정본: docs/plan/18-wellness-coaching.md §4(트랙)·§4-A(문진→플랜)·§5(컴플라).
설계 원칙(경계 설계 상속): 플랜은 **결정적 템플릿**으로 생성 — 벗된 KB(식약처·보건소
일반 생활수칙)에서 문진·밴드로 항목 선택. LLM 자유생성 아님 → 효능표방·처방성 구조적 0.
모든 산출은 coaching_compliance(WC-C)로 한 번 더 백스톱.

P2 범위: 식단 1트랙. 운동·습관은 P3. 영속(coaching_session/plan/checkin, mig018)은 별도 배선.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import coaching_compliance as _cc

# ── 문진 (§4-A.1, 한 번에 한 문항·버튼) ──────────────────────────────
INTAKE_QUESTIONS: Dict[str, List[Dict]] = {
    "diet": [
        {"id": "eatout", "q": "평소 외식·배달 빈도는?", "options": ["거의 매일", "주 2~3회", "드뭄"]},
        {"id": "salty", "q": "짠 음식·국물 선호도는?", "options": ["강함", "보통", "약함"]},
        {"id": "period", "q": "목표 기간은?", "options": ["2주", "1개월", "3개월+"]},
    ],
}

# ── 코칭 KB (식단) — 일반 생활수칙만. 효능·치료·용량 표현 금지(WC-C5 화이트리스트). ──
DIET_KB: List[Dict] = [
    {"key": "soup_half", "text": "국물은 절반만 남기기", "cite": "식약처 나트륨 저감", "tag": "외식"},
    {"key": "ramen_weekly", "text": "라면·면류는 주 1회로 줄이기", "cite": "보건소 영양관리", "tag": "외식"},
    {"key": "processed_down", "text": "가공식품·국물요리 줄이기", "cite": "식약처 나트륨 저감", "tag": "외식"},
    {"key": "sauce_dip", "text": "간장·소스는 찍어 먹기", "cite": "식약처 나트륨 저감", "tag": "짠맛"},
    {"key": "taste_light", "text": "간을 평소보다 싱겁게 하기", "cite": "보건소 영양관리", "tag": "짠맛"},
    {"key": "water_more", "text": "국물 대신 물을 충분히 마시기", "cite": "보건소 영양관리", "tag": "짠맛"},
    {"key": "veggie_add", "text": "끼니마다 채소 한 접시 더하기", "cite": "보건소 영양관리", "tag": "균형"},
]
_KB_BY_KEY = {x["key"]: x for x in DIET_KB}

_BANNER = {
    "경고": "⚠️ 혈압이 경고 구간이에요. 식이 조절은 진료와 병행하시고, 우선 가벼운 수칙부터 시작하세요.",
    "주의": "혈압 주의 구간 — 식이 조절은 진료와 병행하세요.",
}


def get_intake(track: str = "diet") -> List[Dict]:
    """트랙 문진 문항 반환(뷰어 버튼 렌더용)."""
    return INTAKE_QUESTIONS.get(track, [])


def _select_keys(intake: Dict, band: Optional[str]) -> List[str]:
    """문진·밴드 기준 KB 항목 선택(결정적). 경고밴드=2개로 캡(soft)."""
    picks: List[str] = []
    if intake.get("eatout") in ("거의 매일", "주 2~3회"):
        picks += ["soup_half", "ramen_weekly", "processed_down"]
    if intake.get("salty") in ("강함", "보통"):
        picks += ["sauce_dip", "taste_light", "water_more"]
    picks.append("veggie_add")
    seen: set = set()
    ordered = [k for k in picks if not (k in seen or seen.add(k))]
    if not ordered:
        ordered = ["soup_half", "veggie_add"]
    cap = 2 if band == "경고" else 4    # WC-C3: 경고밴드 → 강플랜 보류(soft)
    return ordered[:cap]


def _header(intake: Dict, band: Optional[str]) -> str:
    """상대표현 헤더(§5.2-C) — 본인 신호 라벨 + 문진 요약 + 기간."""
    parts = []
    if band in ("주의", "경고"):
        parts.append(f"혈압 {band} 구간")
    if intake.get("eatout") == "거의 매일":
        parts.append("외식 잦음")
    elif intake.get("eatout") == "주 2~3회":
        parts.append("외식 보통")
    period = intake.get("period", "2주")
    base = " · ".join(parts)
    return (f"{base} 기준 {period} 저염 실천 플랜" if base
            else f"{period} 저염 식생활 플랜")


def generate_plan(track: str, intake: Dict, band: Optional[str] = None) -> Dict:
    """문진+밴드 → 결정적 코칭 플랜(§4-A.4 표준 포맷) + WC-C 백스톱.

    Returns dict: track, header, items[{key,text,cite}], period, band,
                  banner, compliance_action, tone.
    """
    if track != "diet":
        raise ValueError(f"P2 MVP는 식단 트랙만 지원: {track!r}")

    keys = _select_keys(intake or {}, band)
    items = [{"key": k, "text": _KB_BY_KEY[k]["text"], "cite": _KB_BY_KEY[k]["cite"]}
             for k in keys]
    header = _header(intake or {}, band)
    banner = _BANNER.get(band)
    tone = "작게 시작해서 꾸준히 이어가 보면 좋아요."

    # WC-C 백스톱(defense-in-depth) — 헤더+항목 텍스트 스캔
    scan_text = header + " " + " ".join(i["text"] for i in items)
    chk = _cc.check_plan(scan_text, band)
    action = chk["action"]
    if not chk["ok"]:
        # 템플릿이라 정상적으로 도달 불가 — 도달 시 안전 최소 플랜으로 폴백.
        items = [{"key": "veggie_add", "text": _KB_BY_KEY["veggie_add"]["text"],
                  "cite": _KB_BY_KEY["veggie_add"]["cite"]}]
        action = "fallback_" + chk["action"]
    elif band == "경고":
        action = "band_capped"

    return {
        "track": "diet",
        "header": header,
        "items": items,
        "period": (intake or {}).get("period", "2주"),
        "band": band,
        "banner": banner,
        "compliance_action": action,
        "tone": tone,
    }
