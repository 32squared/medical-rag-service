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

# ── 문진·코칭 KB — 정본은 루틴 팩 health_12w(routines/packs/health_12w/v1.json) ──
# 28 루틴 팩 플랫폼 이후 내용은 팩 파일 한 곳에만 있다. 이 모듈은 레거시 /coaching/* 용
# 형태(문항 옵션 = 문자열 목록, KB 항목 = key/text/cite/tag)로 펼쳐 보여줄 뿐이다.
# 공신력 일반 생활수칙만. 효능·치료·용량 표현 금지(WC-C5 화이트리스트) — 팩 lint 가 강제.
import routine_engine as _re
import routine_packs as _rp

_HEALTH = _rp.get(_rp.DEFAULT_PACK_ID)

INTAKE_QUESTIONS: Dict[str, List[Dict]] = {
    t: [{"id": q.id, "q": q.q, "options": [o.label for o in q.options]} for q in qs]
    for t, qs in _HEALTH.intake.items()
}

KB: Dict[str, List[Dict]] = {
    t: [{"key": x.key, "text": x.text, "cite": _HEALTH.source_label(x.cite),
         "tag": (x.tags[0] if x.tags else "")} for x in pool]
    for t, pool in _HEALTH.support_pool.items()
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
    """문진·밴드 기준 KB 항목 선택(결정적) — 팩의 누적 규칙(support_rules)·풀 상한(경고=2)."""
    return _re.plan_keys(track, intake, band, _HEALTH)


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
