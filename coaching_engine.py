"""coaching_engine.py — 웰니스 코칭 엔진 (P2 식단 + P3 운동·습관, 3트랙).

정본: docs/plan/18-wellness-coaching.md §4(트랙)·§4-A(문진→플랜)·§5(컴플라).
설계 원칙(경계 설계 상속): 플랜은 **결정적 템플릿** — 벗된 KB(공신력 일반 생활수칙)에서
문진·밴드로 항목 선택. LLM 자유생성 아님 → 효능표방·처방성 구조적 0.
모든 산출은 coaching_compliance(WC-C)로 백스톱.

트랙별 안전 캡(§5.3): 식단=치료식 금지 / 운동=위험군·경고밴드→clearance·고강도 보류 /
습관=임상라벨·효능 금지. 응급은 진입 차단(라우터·핸드오프 단계).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import coaching_compliance as _cc

# ── 문진 (§4-A, 한 번에 한 문항·버튼) ──────────────────────────────
INTAKE_QUESTIONS: Dict[str, List[Dict]] = {
    "diet": [
        {"id": "eatout", "q": "평소 외식·배달 빈도는?", "options": ["거의 매일", "주 2~3회", "드뭄"]},
        {"id": "salty", "q": "짠 음식·국물 선호도는?", "options": ["강함", "보통", "약함"]},
        {"id": "period", "q": "목표 기간은?", "options": ["2주", "1개월", "3개월+"]},
    ],
    "exercise": [
        {"id": "now", "q": "지금 운동 습관은?", "options": ["거의 안 함", "가끔", "주 3회+"]},
        {"id": "activity", "q": "주로 가능한 활동은?", "options": ["걷기", "홈트", "헬스·유산소"]},
        {"id": "goal", "q": "목표는?", "options": ["활동량 늘리기", "체중", "체력"]},
    ],
    "habit": [
        {"id": "focus", "q": "가장 개선하고 싶은 것은?", "options": ["수면", "스트레스", "금연·절주"]},
        {"id": "reg", "q": "요즘 생활 리듬은?", "options": ["불규칙", "보통", "규칙적"]},
        {"id": "period", "q": "목표 기간은?", "options": ["2주", "1개월"]},
    ],
}

# ── 코칭 KB — 공신력 일반 생활수칙만. 효능·치료·용량 표현 금지(WC-C5 화이트리스트). ──
KB: Dict[str, List[Dict]] = {
    "diet": [
        {"key": "soup_half", "text": "국물은 절반만 남기기", "cite": "식약처 나트륨 저감", "tag": "외식"},
        {"key": "ramen_weekly", "text": "라면·면류는 주 1회로 줄이기", "cite": "보건소 영양관리", "tag": "외식"},
        {"key": "processed_down", "text": "가공식품·국물요리 줄이기", "cite": "식약처 나트륨 저감", "tag": "외식"},
        {"key": "sauce_dip", "text": "간장·소스는 찍어 먹기", "cite": "식약처 나트륨 저감", "tag": "짠맛"},
        {"key": "taste_light", "text": "간을 평소보다 싱겁게 하기", "cite": "보건소 영양관리", "tag": "짠맛"},
        {"key": "water_more", "text": "국물 대신 물을 충분히 마시기", "cite": "보건소 영양관리", "tag": "짠맛"},
        {"key": "veggie_add", "text": "끼니마다 채소 한 접시 더하기", "cite": "보건소 영양관리", "tag": "균형"},
    ],
    "exercise": [
        {"key": "walk_more", "text": "하루 10분 더 걷기부터 시작", "cite": "WHO 신체활동 지침", "tag": "시작"},
        {"key": "stairs", "text": "엘리베이터 대신 계단 이용", "cite": "국민체육진흥 일반지침", "tag": "일상"},
        {"key": "move_break", "text": "한 시간에 한 번 일어나 움직이기", "cite": "WHO 신체활동 지침", "tag": "좌식"},
        {"key": "walk_3x", "text": "주 3회 가벼운 걷기(20~30분)", "cite": "WHO 신체활동 지침", "tag": "유산소"},
        {"key": "stretch", "text": "자기 전 가벼운 스트레칭", "cite": "국민체육진흥 일반지침", "tag": "유연"},
    ],
    "habit": [
        {"key": "sleep_fix", "text": "취침·기상 시간 일정하게 하기", "cite": "질병청 건강생활", "tag": "수면"},
        {"key": "screen_off", "text": "자기 1시간 전 화면 줄이기", "cite": "질병청 건강생활", "tag": "수면"},
        {"key": "caffeine", "text": "오후엔 카페인 줄이기", "cite": "보건소 영양관리", "tag": "수면"},
        {"key": "breathe", "text": "하루 5분 천천히 호흡하기", "cite": "질병청 건강생활", "tag": "스트레스"},
        {"key": "rest", "text": "짧은 휴식을 자주 갖기", "cite": "보건소 건강생활", "tag": "스트레스"},
        {"key": "smoke_help", "text": "보건소 금연클리닉 상담 연계", "cite": "보건소 금연사업", "tag": "금연·절주"},
        {"key": "drink_down", "text": "음주 횟수와 양 줄이기", "cite": "보건소 절주사업", "tag": "금연·절주"},
    ],
}
_KB_BY_KEY = {t: {x["key"]: x for x in items} for t, items in KB.items()}

_TRACK_NOUN = {"diet": "저염 실천", "exercise": "활동 늘리기", "habit": "생활습관"}

# 밴드 배너 — 트랙별(운동은 clearance 추가, §5.3)
_BANNER = {
    "diet": {
        "경고": "⚠️ 혈압이 경고 구간이에요. 식이 조절은 진료와 병행하시고, 우선 가벼운 수칙부터 시작하세요.",
        "주의": "혈압 주의 구간 — 식이 조절은 진료와 병행하세요.",
    },
    "exercise": {
        "경고": "⚠️ 혈압이 경고 구간이에요. 운동 전 의료진 상담(clearance)을 받으시고, 우선 가벼운 활동부터 시작하세요.",
        "주의": "혈압 주의 구간 — 무리한 운동은 피하고 진료와 병행하세요.",
    },
    "habit": {
        "경고": "⚠️ 혈압이 경고 구간이에요. 생활 습관과 함께 진료를 우선 고려하세요.",
        "주의": "혈압 주의 구간 — 생활 습관 관리와 함께 진료를 병행하세요.",
    },
}


def get_intake(track: str = "diet") -> List[Dict]:
    """트랙 문진 문항 반환(뷰어 버튼 렌더용)."""
    return INTAKE_QUESTIONS.get(track, [])


def supported_tracks() -> List[str]:
    return list(KB.keys())


def _select_keys(track: str, intake: Dict, band: Optional[str]) -> List[str]:
    """문진·밴드 기준 KB 항목 선택(결정적). 경고밴드=2개로 캡(soft, WC-C3)."""
    picks: List[str] = []
    if track == "diet":
        if intake.get("eatout") in ("거의 매일", "주 2~3회"):
            picks += ["soup_half", "ramen_weekly", "processed_down"]
        if intake.get("salty") in ("강함", "보통"):
            picks += ["sauce_dip", "taste_light", "water_more"]
        picks.append("veggie_add")
        default = ["soup_half", "veggie_add"]
    elif track == "exercise":
        if intake.get("now") == "거의 안 함":
            picks += ["walk_more", "stairs", "move_break"]
        else:
            picks += ["walk_3x", "stretch", "walk_more"]
        picks.append("stretch")
        default = ["walk_more", "stairs"]
    else:  # habit
        focus = intake.get("focus") or "수면"
        picks += [x["key"] for x in KB["habit"] if x["tag"] == focus]
        picks.append("breathe")
        default = ["sleep_fix", "breathe"]

    seen: set = set()
    ordered = [k for k in picks if not (k in seen or seen.add(k))]
    if not ordered:
        ordered = default
    cap = 2 if band == "경고" else 4
    return ordered[:cap]


def _header(track: str, intake: Dict, band: Optional[str]) -> str:
    """상대표현 헤더(§5.2-C) — 본인 신호 라벨 + 문진 요약 + 기간."""
    parts = []
    if band in ("주의", "경고"):
        parts.append(f"혈압 {band} 구간")
    if track == "diet" and intake.get("eatout") == "거의 매일":
        parts.append("외식 잦음")
    if track == "exercise" and intake.get("now") == "거의 안 함":
        parts.append("활동 적음")
    if track == "habit" and intake.get("focus"):
        parts.append(intake["focus"])
    period = intake.get("period", "2주")
    noun = _TRACK_NOUN[track]
    base = " · ".join(parts)
    return f"{base} 기준 {period} {noun} 플랜" if base else f"{period} {noun} 플랜"


def generate_plan(track: str, intake: Dict, band: Optional[str] = None) -> Dict:
    """문진+밴드 → 결정적 코칭 플랜(§4-A.4 표준 포맷) + WC-C 백스톱."""
    if track not in KB:
        raise ValueError(f"미지원 트랙: {track!r} (지원: {list(KB)})")

    intake = intake or {}
    keys = _select_keys(track, intake, band)
    kb = _KB_BY_KEY[track]
    items = [{"key": k, "text": kb[k]["text"], "cite": kb[k]["cite"]} for k in keys]
    header = _header(track, intake, band)
    banner = _BANNER[track].get(band)
    tone = "작게 시작해서 꾸준히 이어가 보면 좋아요."

    scan_text = header + " " + " ".join(i["text"] for i in items)
    chk = _cc.check_plan(scan_text, band)
    action = chk["action"]
    if not chk["ok"]:
        items = [{"key": keys[0], "text": kb[keys[0]]["text"], "cite": kb[keys[0]]["cite"]}]
        action = "fallback_" + chk["action"]
    elif band == "경고":
        action = "band_capped"

    return {
        "track": track,
        "header": header,
        "items": items,
        "period": intake.get("period", "2주"),
        "band": band,
        "banner": banner,
        "compliance_action": action,
        "tone": tone,
    }
