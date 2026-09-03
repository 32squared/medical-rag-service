"""archetype_engine.py — 오늘의 나 재미 레이어 순수 계산.

정본: docs/design/todays-me-mockups/00-concept-brief.md §3·§4, 02-dev-requirements.md §5.

원칙
  - 완료 트랙 **조합만**으로 아키타입을 정한다. 안 한 트랙·못했어요·해당없음은 계산에 없다.
  - 미완료 개수·결석 일수·타인 비교값은 어떤 반환값에도 넣지 않는다(무비난).
  - 목표치·환산 계수는 이 파일의 상수 한 곳에서만 읽는다(E1 에스컬레이션 시 여기만 바꾼다).
  - 어떤 입력에도 예외를 던지지 않는다(홈 화면 1콜에 끼어드는 계산이다).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

KST = timezone(timedelta(hours=9))

# ── 트랙·목표(잠정, 교차검수 A2 / E1) ───────────────────────────────
TRACKS = ("diet", "exercise", "habit")          # 식이 기록 / 활동 기록 / 생활 리듬
GOALS = {"water_cups": 6, "steps": 6000, "mind_sessions": 1}
WAKE = {"water_cups": 1, "steps": 1000}         # 깨어남(≠완료) 임계
WATER_CUP_ML = 200
STEPS_STALE_MIN = 30                            # 교차검수 C2
CARD_LOCK_GRACE_MIN = 10                        # 정본 25 E01 유예 = 카드 잠금 유예
BEDTIME_PREV_NIGHT_BEFORE = 5                   # 05:00 이전 취침 → 전날 밤(C1)

# ── 아키타입 사전 7종 (브리프 §4) ──────────────────────────────────
ARCHETYPES: Dict[str, Dict] = {
    "hydration_king":     {"combo": ("diet",),                       "name_en": "Hydration King",     "name_ko": "수분왕",
                           "lore": "오늘 몸의 70%를 책임진 사람",        "bg": "#AFC9F5", "elements": ("water",)},
    "step_wizard":        {"combo": ("exercise",),                   "name_en": "Step Wizard",        "name_ko": "걸음술사",
                           "lore": "지도 위에 오늘 하루를 그렸어요",      "bg": "#FFD84D", "elements": ("bolt",)},
    "mindful_warrior":    {"combo": ("habit",),                      "name_en": "Mindful Warrior",    "name_ko": "마음의 전사",
                           "lore": "폰보다 먼저 눈을 감은 자",           "bg": "#CDBFF7", "elements": ("moon",)},
    "sunny_runner":       {"combo": ("diet", "exercise"),            "name_en": "Sunny Runner",       "name_ko": "햇살 러너",
                           "lore": "마시고 달리는 낮의 사람",            "bg": "#FFC98F", "elements": ("water", "bolt")},
    "night_owl_reformed": {"combo": ("exercise", "habit"),           "name_en": "Night Owl, Reformed", "name_ko": "개과천선 올빼미",
                           "lore": "움직이고 일찍 잔 기적",              "bg": "#BFE8CF", "elements": ("bolt", "moon")},
    "zen_barista":        {"combo": ("diet", "habit"),               "name_en": "Zen Barista",        "name_ko": "젠 바리스타",
                           "lore": "물 한 잔, 숨 한 번",                "bg": "#E4EBC7", "elements": ("water", "moon")},
    "balance_monk":       {"combo": ("diet", "exercise", "habit"),   "name_en": "Balance Monk",       "name_ko": "밸런스 수도승",
                           "lore": "오늘 세 가지 모두 완료",             "bg": "#F5A8D8", "elements": ("water", "bolt", "moon")},
}
_COMBO_INDEX = {frozenset(v["combo"]): k for k, v in ARCHETYPES.items()}

# ── 웰니스 타입 5종 (브리프 §4-2·§4-3) ──────────────────────────────
WELLNESS_TYPES: Dict[str, Dict] = {
    "miracle_morning_dreamer": {"name_ko": "새벽 감성 야망가", "name_en": "Miracle Morning Dreamer",
                                "one_liner": "새벽 5시에 물 마시고 명상하지만 저녁 8시면 방전", "default_theme": "lavender"},
    "micro_wellness_sloth":    {"name_ko": "마이크로 웰니스 나무늘보", "name_en": "Micro-Wellness Sloth",
                                "one_liner": "헬스장 대신 이불 정리·3분 호흡으로 마음의 평화를 지킴", "default_theme": "forest"},
    "healthy_pleasure_foodie": {"name_ko": "헬시 플레저 미식가", "name_en": "Healthy Pleasure Foodie",
                                "one_liner": "운동 뒤 고단백 간식과 제로 디저트로 스스로 보상", "default_theme": "coral"},
    "ritual_fairy":            {"name_ko": "유리멘탈 리추얼 요정", "name_en": "Ritual Fairy",
                                "one_liner": "향·일기·호흡으로 무너진 마음을 정성껏 복구", "default_theme": "lavender"},
    "baby_godsaeng":           {"name_ko": "갓생 신생아", "name_en": "Baby God-Saeng",
                                "one_liner": "물 한 잔·비타민 하나에도 뿌듯한 시작 단계", "default_theme": "coral"},
}
_TYPE_ORDER = ("miracle_morning_dreamer", "micro_wellness_sloth", "healthy_pleasure_foodie",
               "ritual_fairy", "baby_godsaeng")
WELLNESS_QUIZ: List[Dict] = [
    {"id": "q1", "text": "하루 중 가장 나다운 시간은?",
     "options": ["해 뜨기 전 새벽", "침대 위 아무 때나", "운동 끝난 직후", "밤, 혼자만의 시간", "아직 찾는 중"]},
    {"id": "q2", "text": "오늘 딱 하나만 한다면?",
     "options": ["물 한 잔과 명상", "이불 정리와 3분 호흡", "운동하고 맛있는 것", "향 피우고 일기 쓰기", "비타민 하나 챙기기"]},
    {"id": "q3", "text": "힘든 날의 나는?",
     "options": ["일찍 자고 새벽에 다시", "아무것도 안 하고 쉼", "땀 빼고 맛있게 먹기", "글로 마음 풀기", "하나만 하고 나를 칭찬"]},
    {"id": "q4", "text": "나에게 웰니스란?",
     "options": ["목표", "평화", "즐거움", "회복", "시작"]},
]
CARD_THEMES = ("coral", "lavender", "forest")

# ── 환산 계수 (교차검수 A1) ─────────────────────────────────────────
_CONVERSION = {
    "water_cups":  (2,   "= 작은 화분 {n}개"),
    "steps":       (3000, "= 한강 다리 {n}개"),
    "mindful_min": (3.5, "= 노래 {n}곡"),
}
_CONVERSION_CAP = {"mindful_min": 8}


# ══════════════════════════ 시간 규칙 ══════════════════════════
def applied_date(client_ts: Optional[str], server_now: Optional[datetime] = None) -> str:
    """정본 25 E01: client_ts 가 23:50~23:59:59 이고 서버가 00:00~00:10 이면 전날로 귀속.
    그 외는 서버 KST 날짜. 파싱 실패 시 서버 날짜."""
    now = (server_now or datetime.now(timezone.utc)).astimezone(KST)
    today = now.strftime("%Y-%m-%d")
    try:
        if not client_ts:
            return today
        c = datetime.fromisoformat(str(client_ts).replace("Z", "+00:00"))
        c = c.astimezone(KST) if c.tzinfo else c.replace(tzinfo=KST)
        if (c.hour == 23 and c.minute >= 50) and (now.hour == 0 and now.minute <= CARD_LOCK_GRACE_MIN):
            return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        pass
    return today


def bedtime_metric_date(bedtime_iso: Optional[str]) -> Optional[str]:
    """취침 시각이 05:00 이전이면 전날 밤 기록으로 귀속(생활 리듬 한정, C1)."""
    try:
        b = datetime.fromisoformat(str(bedtime_iso).replace("Z", "+00:00"))
        b = b.astimezone(KST) if b.tzinfo else b.replace(tzinfo=KST)
        if b.hour < BEDTIME_PREV_NIGHT_BEFORE:
            b = b - timedelta(days=1)
        return b.strftime("%Y-%m-%d")
    except Exception:
        return None


def card_lock_at(metric_date: str) -> str:
    """카드 재편집 마감 = 기록일 다음날 00:10 KST (C5)."""
    try:
        d = datetime.strptime(metric_date[:10], "%Y-%m-%d").replace(tzinfo=KST)
        return (d + timedelta(days=1, minutes=CARD_LOCK_GRACE_MIN)).isoformat()
    except Exception:
        return metric_date


def steps_stale(synced_at: Optional[str], now: Optional[datetime] = None) -> bool:
    if not synced_at:
        return True
    try:
        s = datetime.fromisoformat(str(synced_at).replace("Z", "+00:00"))
        if not s.tzinfo:
            s = s.replace(tzinfo=KST)
        n = now or datetime.now(timezone.utc)
        return (n - s) > timedelta(minutes=STEPS_STALE_MIN)
    except Exception:
        return True


# ══════════════════════════ 완료·깨어남·아키타입 ══════════════════════════
def _i(v, default=0) -> int:
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def track_state(m: Optional[Dict]) -> Dict[str, Dict]:
    """daily_metrics 행 → 트랙별 {awake, complete, ...}. 깨어남 ≠ 완료(A2)."""
    m = m or {}
    cups = max(0, _i(m.get("water_cups")))
    steps = m.get("steps")
    steps_i = _i(steps) if steps is not None else None
    steps_src = m.get("steps_source") or "none"
    confirmed = bool(_i(m.get("steps_confirmed")))
    sessions = max(0, _i(m.get("mind_sessions")))
    seconds = max(0, _i(m.get("mind_seconds")))
    return {
        "water": {"cups": cups, "goal": GOALS["water_cups"],
                  "awake": cups >= WAKE["water_cups"], "complete": cups >= GOALS["water_cups"]},
        "steps": {"value": steps_i, "goal": GOALS["steps"], "source": steps_src,
                  "synced_at": m.get("steps_synced_at"), "stale": steps_stale(m.get("steps_synced_at")) if steps_src == "auto" else False,
                  "awake": (steps_i is not None and steps_i >= WAKE["steps"]) or steps_src == "manual",
                  "complete": (steps_i is not None and steps_i >= GOALS["steps"]) or confirmed},
        "mind": {"seconds": seconds, "sessions": sessions,
                 "awake": seconds > 0 or sessions > 0, "complete": sessions >= GOALS["mind_sessions"]},
    }


def completed_tracks(m: Optional[Dict]) -> List[str]:
    st = track_state(m)
    out = []
    if st["water"]["complete"]:
        out.append("diet")
    if st["steps"]["complete"]:
        out.append("exercise")
    if st["mind"]["complete"]:
        out.append("habit")
    return out


def archetype_for(tracks: Sequence[str]) -> Optional[str]:
    """완료 트랙 조합 → archetype_id. 0개면 None(리빌 없음)."""
    key = frozenset(t for t in (tracks or ()) if t in TRACKS)
    return _COMBO_INDEX.get(key) if key else None


def archetype_info(archetype_id: Optional[str]) -> Optional[Dict]:
    a = ARCHETYPES.get(archetype_id or "")
    if not a:
        return None
    return {"archetype_id": archetype_id, "name_en": a["name_en"], "name_ko": a["name_ko"],
            "lore": a["lore"], "bg": a["bg"], "elements": list(a["elements"])}


def fun_layer_allowed(band: Optional[str]) -> bool:
    """경고·응급 밴드는 재미 레이어 전체 차단(정본 §0-3, FR-C05)."""
    return band not in ("경고", "응급")


# ══════════════════════════ 환산·태그·하이라이트 ══════════════════════════
def conversion_text(kind: str, value: Optional[int]) -> Optional[str]:
    """A1 계수. 환산 수량 0 이면 문구 없음(미달 표시가 되기 때문)."""
    if value is None or kind not in _CONVERSION:
        return None
    unit, tpl = _CONVERSION[kind]
    n = int(math.floor(max(0, _i(value)) / unit))
    cap = _CONVERSION_CAP.get(kind)
    if cap:
        n = min(n, cap)
    return tpl.format(n=n) if n > 0 else None


def metrics_rows(m: Optional[Dict], tracks: Optional[Sequence[str]] = None) -> List[Dict]:
    """화면 2·카드용 지표 행. 완료 트랙 우선 순서(식이→활동→리듬), 값 0·미측정은 행을 만들지 않는다."""
    st = track_state(m)
    rows: List[Dict] = []
    if st["water"]["cups"] > 0:
        rows.append({"kind": "water_cups", "value": st["water"]["cups"], "unit_label": "컵의 물",
                     "conversion_text": conversion_text("water_cups", st["water"]["cups"])})
    if st["steps"]["value"]:
        rows.append({"kind": "steps", "value": st["steps"]["value"], "unit_label": "걸음",
                     "conversion_text": conversion_text("steps", st["steps"]["value"]),
                     "stale": st["steps"]["stale"]})
    mins = st["mind"]["seconds"] // 60
    if mins > 0:
        rows.append({"kind": "mindful_min", "value": mins, "unit_label": "분",
                     "conversion_text": conversion_text("mindful_min", mins)})
    return rows


def why_tags(m: Optional[Dict], tracks: Sequence[str]) -> List[str]:
    """'왜 이 캐릭터?' 태그 ≤3 — 완료 트랙만, 안 한 것 언급 금지(spec-03 §7)."""
    st = track_state(m)
    tags = []
    if "diet" in tracks:
        tags.append(f"물 {st['water']['cups']}컵")
    if "exercise" in tracks:
        v = st["steps"]["value"]
        tags.append(f"{v:,}걸음" if v else "활동 완료")
    if "habit" in tracks:
        mins = max(1, st["mind"]["seconds"] // 60)
        tags.append(f"마음챙김 {mins}분")
    return tags[:3]


_HIGHLIGHT = {"water": "이번 주 물을 가장 많이 마신 날",
              "steps": "이번 주 가장 많이 걸은 날",
              "mind": "이번 주 가장 오래 마음챙김한 날"}


def highlight(today: Optional[Dict], history: Sequence[Dict], week_record_days: int = 0) -> Dict:
    """spec-02 §5-5: 오늘 > max(직전 6일) 인 지표 1개(트랙 순서). 동률 제외. 폴백 F1~F3."""
    t = track_state(today)
    hist = [track_state(h) for h in (history or [])]

    def _best(getter):
        vals = [getter(h) for h in hist]
        vals = [v for v in vals if v is not None]
        return max(vals) if vals else None

    cands = [("water", t["water"]["cups"] or None, _best(lambda h: h["water"]["cups"] or None)),
             ("steps", t["steps"]["value"], _best(lambda h: h["steps"]["value"])),
             ("mind", t["mind"]["seconds"] or None, _best(lambda h: h["mind"]["seconds"] or None))]
    for kind, tv, best in cands:
        if tv is not None and (best is None or tv > best) and (best is not None):
            return {"type": kind, "text": _HIGHLIGHT[kind]}
    if len(completed_tracks(today)) == 3:
        return {"type": "f1", "text": "세 가지를 모두 기록한 날"}
    if week_record_days >= 2:
        return {"type": "f2", "text": f"이번 주 {week_record_days}일째 기록한 날"}
    return {"type": "f3", "text": "기록이 쌓이면 여기에 보여드릴게요"}


# ══════════════════════════ 희귀도 ══════════════════════════
RARITY_MIN_DENOMINATOR = 100        # 교차검수 C3


def rarity_pct(user_count: Optional[int], denominator: Optional[int]) -> Optional[int]:
    """사용자 단위 분포 %. 분모 < 100 이면 None(줄 자체 숨김). 1% 미만은 0 이 아니라 1 미만 표기용 -1? → 0 반환 후 UI 가 '1% 미만'."""
    n, d = _i(user_count), _i(denominator)
    if d < RARITY_MIN_DENOMINATOR or n < 0:
        return None
    return int(round(n / d * 100)) if d else None


def rarity_text(pct: Optional[int]) -> Optional[str]:
    if pct is None:
        return None
    if pct < 1:
        return "이번 달 이 캐릭터 만난 사람 1% 미만"
    return f"이번 달 이 캐릭터 만난 사람 {pct}%"


# ══════════════════════════ 웰니스 타입 ══════════════════════════
def assign_wellness_type(answers: Sequence[int]) -> Optional[str]:
    """4문항 최다 득표, 동점이면 Q4 답 우선(브리프 §4-3). 유효하지 않으면 None."""
    try:
        a = [int(x) for x in answers]
    except Exception:
        return None
    if len(a) != len(WELLNESS_QUIZ) or any(x < 0 or x >= len(_TYPE_ORDER) for x in a):
        return None
    votes = {t: 0 for t in _TYPE_ORDER}
    for x in a:
        votes[_TYPE_ORDER[x]] += 1
    top = max(votes.values())
    tied = [t for t in _TYPE_ORDER if votes[t] == top]
    if len(tied) == 1:
        return tied[0]
    q4 = _TYPE_ORDER[a[-1]]
    return q4 if q4 in tied else tied[0]


def wellness_type_info(type_id: Optional[str]) -> Optional[Dict]:
    t = WELLNESS_TYPES.get(type_id or "")
    if not t:
        return None
    return {"type_id": type_id, **t, "label": f"{t['name_ko']} 타입"}


# ══════════════════════════ 공유 카드 화이트리스트 ══════════════════════════
CARD_ALLOWED_KEYS = frozenset({
    "date_label", "brand_label", "metrics", "archetype_en", "archetype_ko", "archetype_lore",
    "rarity_pct", "theme_id", "stickers", "comment", "hide_numbers", "wellness_type_label",
})
CARD_FORBIDDEN_SUBSTRINGS = ("bp", "glucose", "band", "grade", "streak", "rank", "percentile",
                             "missed", "name", "profile")
CARD_MAX_STICKERS = 6
CARD_MAX_PER_STICKER = 3
CARD_STICKER_TYPES = ("star", "cloud", "bolt", "drop", "moon")
CARD_COMMENT_MAX = 20


def build_card_payload(*, metric_date: str, m: Optional[Dict], archetype_id: Optional[str],
                       rarity: Optional[int], theme_id: str, stickers: Sequence[Dict],
                       comment: Optional[str], hide_numbers: bool,
                       wellness_type_id: Optional[str], band: Optional[str]) -> Optional[Dict]:
    """열거형 화이트리스트 페이로드(spec-04 §4-2). 밴드 게이트·아키타입 없음이면 None."""
    if not fun_layer_allowed(band):
        return None
    info = archetype_info(archetype_id)
    if not info:
        return None
    try:
        d = datetime.strptime(metric_date[:10], "%Y-%m-%d")
        date_label = d.strftime("%m.%d %a").upper()
    except Exception:
        date_label = metric_date
    wt = wellness_type_info(wellness_type_id)
    payload = {
        "date_label": date_label,
        "brand_label": "TODAY'S ME",
        "metrics": [] if hide_numbers else [
            {"kind": r["kind"], "value": int(r["value"]), "unit_label": r["unit_label"]}
            for r in metrics_rows(m)[:3]],
        "archetype_en": info["name_en"], "archetype_ko": info["name_ko"], "archetype_lore": info["lore"],
        "rarity_pct": None if hide_numbers else rarity,
        "theme_id": theme_id if theme_id in CARD_THEMES else "coral",
        "stickers": [s for s in (stickers or [])][:CARD_MAX_STICKERS],
        "comment": (comment or None),
        "hide_numbers": bool(hide_numbers),
        "wellness_type_label": wt["label"] if wt else None,
    }
    assert_card_payload(payload)
    return payload


def assert_card_payload(payload: Dict) -> None:
    """미지 키·금지 키 이름이 하나라도 있으면 렌더 거부(fail-closed)."""
    unknown = set(payload) - CARD_ALLOWED_KEYS
    if unknown:
        raise ValueError(f"card_payload_unknown_keys:{sorted(unknown)}")
    for k in payload:
        lk = k.lower()
        if any(f in lk for f in CARD_FORBIDDEN_SUBSTRINGS) and k not in CARD_ALLOWED_KEYS:
            raise ValueError(f"card_payload_forbidden_key:{k}")
    if len(payload.get("metrics") or []) > 3:
        raise ValueError("card_payload_too_many_metrics")
    c = payload.get("comment")
    if c and len(c) > CARD_COMMENT_MAX:
        raise ValueError("card_payload_comment_too_long")


def validate_stickers(stickers: Sequence[Dict]) -> Optional[str]:
    """None 이면 OK, 아니면 오류 코드."""
    st = list(stickers or [])
    if len(st) > CARD_MAX_STICKERS:
        return "sticker_limit"
    counts: Dict[str, int] = {}
    for s in st:
        t = (s or {}).get("type")
        if t not in CARD_STICKER_TYPES:
            return "sticker_type"
        counts[t] = counts.get(t, 0) + 1
        if counts[t] > CARD_MAX_PER_STICKER:
            return "sticker_limit"
        for key in ("x", "y"):
            try:
                v = float(s.get(key, 0))
            except Exception:
                return "sticker_position"
            if v < 0 or v > 1:
                return "sticker_position"
    return None
