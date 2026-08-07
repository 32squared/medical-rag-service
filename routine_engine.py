"""routine_engine.py — 12주 루틴 프로그램 엔진 (순수 함수).

정본: docs/plan/25-routine-transition-spec.md §B(커리큘럼)·§E-4(상수)·§H-4(컴플라 게이트).

설계 원칙(coaching_engine 상속):
  - **결정적 템플릿**. LLM 자유생성 아님 → 효능표방·처방성 구조적 0.
  - 모든 행동에 공신력 출처(cite) 필수.
  - 산출은 coaching_compliance(WC-C)로 백스톱(defense-in-depth).

전략 근거(사용자확대전략 rev6): 정보형(Q&A)은 트리거가 앱 밖에 있어 자연빈도 월 1회 미만.
루틴형으로 전환해 **매일 데이터가 생성되는 구조**를 만든다. 그래서 메인 행동은
'읽고 실천하는 수칙'이 아니라 **기록형 메타 행동**(값·태그가 남는 행동)이다(스펙 C6).
보조 행동은 coaching_engine.KB(생활수칙)를 재사용한다.

의료법 27조: 진단·처방·효능·용량 표현 금지. 밴드는 '구간 안내'이며 판정이 아니다.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import coaching_compliance as _cc

CURRICULUM_VERSION = 1
WEEKS_TOTAL = 12

# ── 단계(스펙 C1: 2/4/4/2) ─────────────────────────────────────────
PHASES: List[Tuple[str, int, int]] = [
    ("정착기", 1, 2),
    ("확장기", 3, 6),
    ("내재화기", 7, 10),
    ("전환기", 11, 12),
]

TRACKS = ("diet", "exercise", "habit")

# 검진 신호 → focus → 트랙(스펙 B-4). focus 는 근거문구·보조항목 가중에만 사용.
FOCUS_TRACK = {
    "bp": "diet", "glucose": "diet",
    "weight_activity": "exercise",
    "sleep_stress": "habit",
}

# ── 주차 메타(스펙 B-2) ────────────────────────────────────────────
#   goal_days: 주간 미션 목표일수 — 전환 판정(70/40)의 분모
#   support:   보조 항목 슬롯 상한(밴드 캡과 min 연산)
WEEKS: List[Dict] = [
    {"w": 1,  "theme": "앵커에 붙이기 — 30초면 끝",        "goal_days": 3, "support": 0,
     "unlock": "badge:작심삼일 격파", "mission": "7일 중 3일 이상, 같은 앵커 뒤에 기록. 이번 주는 항목 1개 고정 — 더 얹지 않는 것이 미션"},
    {"w": 2,  "theme": "같은 시각·같은 자리",              "goal_days": 5, "support": 0,
     "unlock": "badge:일주일", "mission": "7일 중 5일 같은 시각에 기록 + 알림 시각 1개 확정"},
    {"w": 3,  "theme": "내 기준선 읽기",                   "goal_days": 5, "support": 1,
     "unlock": "추세 카드", "mission": "7일 중 5일 기록 + 내 7일 범위 1회 확인 + 궁금증 1개 상담"},
    {"w": 4,  "theme": "방아쇠 찾기 — 언제 무너지는지",     "goal_days": 5, "support": 1,
     "unlock": "milestone:4주 완주", "mission": "7일 중 5일 태그 + 자주 무너지는 상황 1개 확인"},
    {"w": 5,  "theme": "바깥에서도 되게 — 미리 정해두기",   "goal_days": 5, "support": 1,
     "unlock": "상황별 대체 행동 카드팩", "mission": "바깥 일정이 있는 날 중 2일, 예약한 대체 행동 실행"},
    {"w": 6,  "theme": "하나 더 얹기 — 두 번째 행동",       "goal_days": 5, "support": 1,
     "unlock": "난이도 자기조절", "mission": "7일 중 5일 두 행동 연달아 (경고 구간은 추가 없이 기록 요일 1일 늘리기)"},
    {"w": 7,  "theme": "무너진 날 복구 — 두 번 연속은 없다", "goal_days": 5, "support": 2,
     "unlock": "스트릭 프리즈", "mission": "두 번 연속 거르지 않기 + 못 한 날 사유 태그 1개"},
    {"w": 8,  "theme": "지루함 넘기기 — 방식만 바꾸기",     "goal_days": 5, "support": 2,
     "unlock": "3일 미니 챌린지", "mission": "7일 중 5일 실행 + 3일 미니 챌린지 1개 완주"},
    {"w": 9,  "theme": "환경 바꾸기 — 의지 대신 배치",      "goal_days": 5, "support": 2,
     "unlock": "milestone:2개월", "mission": "환경 변경 3개 적용하고 유지"},
    {"w": 10, "theme": "내 데이터로 나를 설명하기",          "goal_days": 5, "support": 2,
     "unlock": "개인 요약 카드", "mission": "내 패턴 요약 3문장 확정"},
    {"w": 11, "theme": "밖으로 가져가기 — 진료·검진에 쓰기", "goal_days": 4, "support": 1,
     "unlock": "진료 준비 시트", "mission": "질문 3개 + 내 기록 요약 1장 준비 + 검진 대상·주기 확인"},
    {"w": 12, "theme": "내 유지 루틴 확정 — 적게 남기기",   "goal_days": 4, "support": 1,
     "unlock": "trophy:12주 완주", "mission": "다음 3개월 유지 루틴 1~2개 확정"},
]
_WEEK_BY_NO = {x["w"]: x for x in WEEKS}

# ── 입력 위젯(값은 '라벨만' — 원시수치·자유텍스트 미수집, 스펙 E-1) ──
_IN_TAP = {"kind": "tap", "options": []}
_IN_COMPARE = {"kind": "choice", "options": ["비슷", "높음", "낮음"]}
_IN_TAG = {"kind": "choice", "options": ["평소대로", "야근", "회식·외식", "잠 부족"]}
_IN_SUB = {"kind": "choice", "options": ["국물 절반 남기기", "단 음료 대신 물", "한 정거장 걷기", "해당없음"]}
_IN_CONFIRM = {"kind": "choice", "options": ["맞아요", "조금 달라요"]}
_IN_VARY = {"kind": "choice", "options": ["장소를 바꿈", "순서를 바꿈", "형태를 바꿈"]}
_IN_ENV = {"kind": "choice", "options": ["잘 보이는 곳으로", "안 보이는 곳으로", "미리 꺼내둠"]}
_IN_QUESTION = {"kind": "choice", "options": [
    "요즘 기록을 보면 무엇을 더 확인해야 할까요?",
    "생활습관 중 먼저 바꿀 것은 무엇인가요?",
    "다음 검진에서 눈여겨볼 항목은 무엇인가요?"]}

_TIME_OPTS = {
    "diet": ["18시 이전", "18~20시", "20~22시", "22시 이후"],
    "exercise": ["했어요", "가볍게 움직였어요", "못 했어요"],
    "habit": ["22시 이전", "22~24시", "24시 이후"],
}

# ── 메인 행동(기록형) — 주차 × 트랙 (스펙 B-2 / C6) ─────────────────
_CITE = {
    "kdca": "질병관리청 국가건강정보포털 건강생활실천",
    "phc": "지역보건소 건강생활실천사업",
    "nhis": "국민건강보험공단 일반건강검진 결과 안내",
    "mfds": "식품의약품안전처 나트륨·당류 저감 실천",
    "who": "WHO 신체활동 지침",
    "nutri": "지역보건소 영양관리사업",
    "checkup": "국민건강보험공단 일반건강검진 안내",
}


def _mk(aid, text, cite, minutes, inp):
    return {"id": aid, "text": text, "cite": cite, "minutes": minutes, "input": inp}


# 주차별 트랙 변주. 1주차만 트랙별 문구가 크게 다르고, 이후는 '기록 대상'만 다르다.
_W1 = {
    "diet": _mk("w1:log_meal_time", "저녁 약·양치 직후 앱을 열고 오늘 저녁 식사 시각을 1탭으로 남기세요(30초).",
                _CITE["kdca"], 1, {"kind": "choice", "options": _TIME_OPTS["diet"]}),
    "exercise": _mk("w1:log_activity", "매일 하는 일(양치·세수) 직후 오늘 몸을 움직였는지 1탭으로 남기세요(30초).",
                    _CITE["who"], 1, {"kind": "choice", "options": _TIME_OPTS["exercise"]}),
    "habit": _mk("w1:log_sleep_time", "잠자리에 들기 전 오늘 취침 시각을 1탭으로 남기세요(30초).",
                 _CITE["kdca"], 1, {"kind": "choice", "options": _TIME_OPTS["habit"]}),
}
_TARGET = {"diet": "식사 시각", "exercise": "활동 여부", "habit": "취침 시각"}


def _week_actions(w: int) -> Dict[str, Dict]:
    """주차 w 의 트랙별 메인 행동."""
    if w == 1:
        return dict(_W1)
    out = {}
    for t in TRACKS:
        tgt = _TARGET[t]
        if w == 2:
            a = _mk(f"w2:log_same_time", f"어제와 같은 시각(±30분)·같은 자리에서 오늘 {tgt}을(를) 기록하세요(30초).",
                    _CITE["kdca"], 1, {"kind": "choice", "options": _TIME_OPTS[t]})
        elif w == 3:
            a = _mk("w3:record_compare", f"오늘 {tgt}을(를) 기록한 뒤 7일 흐름을 5초 보고, 오늘이 내 평소보다 어떤지 하나만 탭하세요(40초).",
                    _CITE["nhis"], 1, _IN_COMPARE)
        elif w == 4:
            a = _mk("w4:record_tag", f"오늘 {tgt}을(를) 기록하면서 오늘 상황 태그를 하나 고르세요(10초).",
                    _CITE["phc"], 1, _IN_TAG)
        elif w == 5:
            a = _mk("w5:preplan_sub", "바깥 일정이 있는 날은 그날의 대체 행동 하나를 미리 골라 예약하세요. 해당 없는 날은 [해당없음](30초).",
                    _CITE["mfds"] if t == "diet" else _CITE["who"], 1, _IN_SUB)
        elif w == 6:
            a = _mk("w6:stack_second", f"오늘 {tgt}을(를) 기록한 직후, 아래 보조 행동 하나를 이어서 하세요(총 2분).",
                    _CITE["who"], 2, _IN_TAP)
        elif w == 7:
            a = _mk("w7:pass_or_log", f"오늘 {tgt}을(를) 기록하세요. 못 하는 날은 [오늘은 패스]를 눌러 기록을 이어가세요(5초).",
                    _CITE["kdca"], 1, _IN_TAP)
        elif w == 8:
            a = _mk("w8:vary_once", "같은 행동을 오늘 하루만 다른 방식으로 해보고, 무엇을 바꿨는지 고르세요(2분).",
                    _CITE["kdca"], 2, _IN_VARY)
        elif w == 9:
            a = _mk("w9:env_change", "실천을 방해하는 물건이나 배치를 하나 바꾸고 무엇을 했는지 고르세요(3분).",
                    _CITE["nutri"] if t == "diet" else _CITE["phc"], 3, _IN_ENV)
        elif w == 10:
            a = _mk("w10:confirm_pattern", "앱이 정리한 '내 패턴 한 줄'을 확인하고, 맞으면 확인 다르면 수정을 고르세요(30초).",
                    _CITE["checkup"], 1, _IN_CONFIRM)
        elif w == 11:
            a = _mk("w11:save_question", "다음 진료·검진 때 물어볼 질문을 하나 골라 저장하세요(1분).",
                    _CITE["checkup"], 1, _IN_QUESTION)
        else:  # 12
            a = _mk("w12:pick_keeper", "12주 동안 가장 잘 지킨 행동 하나에 '유지 루틴' 표시를 하세요(30초).",
                    _CITE["kdca"], 1, _IN_TAP)
        out[t] = a
    return out


ROUTINE_ACTIONS: Dict[Tuple[int, str], Dict] = {
    (w["w"], t): a for w in WEEKS for t, a in _week_actions(w["w"]).items()
}

# ── 상담 재진입 질문칩(스펙 B-6) — 주차별 ──────────────────────────
ASK_CHIPS: Dict[int, List[str]] = {
    1: ["기록은 언제 하는 게 좋을까요?", "매일 하기 어려우면 어떻게 하나요?", "이 기록이 왜 도움이 되나요?"],
    2: ["같은 시각에 재는 게 왜 중요한가요?", "알림은 몇 시가 적당할까요?", "주말엔 어떻게 하나요?"],
    3: ["아침과 저녁 기록이 다른 건 왜인가요?", "기록은 얼마나 오래 해야 하나요?", "평소보다 높은 날은 뭘 보면 되나요?"],
    4: ["잠이 부족하면 어떤 영향이 있나요?", "야근이 잦을 때 실천법이 있을까요?", "주말에만 무너지는 건 왜일까요?"],
    5: ["회식 자리에서 국물은 왜 자주 언급되나요?", "외식이 잦을 때의 실천법은?", "단 음료 대신 무엇이 좋을까요?"],
    6: ["두 가지를 한 번에 하면 부담되지 않을까요?", "물은 얼마나 마시는 게 좋을까요?", "계단 오르기는 어떤 도움이 되나요?"],
    7: ["며칠 걸렀는데 처음부터 다시 해야 하나요?", "쉬는 날을 두는 게 나을까요?", "다시 시작할 때 요령이 있나요?"],
    8: ["같은 걸 반복하면 효과가 줄어드나요?", "지루할 때 바꿔볼 만한 게 있나요?", "짧게 해도 의미가 있나요?"],
    9: ["환경을 바꾸는 게 왜 도움이 되나요?", "집에서 바꾸기 쉬운 건 뭐가 있나요?", "가족과 함께하면 좋을까요?"],
    10: ["제 기록에서 무엇을 읽을 수 있나요?", "패턴을 어떻게 활용하나요?", "기록을 진료에 어떻게 쓰나요?"],
    11: ["진료 때 무엇을 물어보면 좋을까요?", "검진은 얼마 주기로 받나요?", "기록을 어떻게 보여드리면 되나요?"],
    12: ["3개월 뒤에는 무엇을 이어가면 좋을까요?", "유지 루틴은 몇 개가 적당한가요?", "다음 목표는 어떻게 정하나요?"],
}

# ── 밴드 배너(coaching_engine._BANNER 와 톤 일치) ──────────────────
_BANNER = {
    "diet": {
        "경고": "⚠️ 측정값이 경고 구간이에요. 식이 조절은 진료와 병행하시고, 우선 기록부터 가볍게 이어가세요.",
        "주의": "측정값이 주의 구간이에요 — 식이 조절은 진료와 병행하세요.",
    },
    "exercise": {
        "경고": "⚠️ 측정값이 경고 구간이에요. 운동 전 의료진 상담(clearance)을 받으시고, 우선 기록부터 이어가세요.",
        "주의": "측정값이 주의 구간이에요 — 무리한 운동은 피하고 진료와 병행하세요.",
    },
    "habit": {
        "경고": "⚠️ 측정값이 경고 구간이에요. 생활 습관과 함께 진료를 우선 고려하세요.",
        "주의": "측정값이 주의 구간이에요 — 생활 습관 관리와 함께 진료를 병행하세요.",
    },
}


# ══════════════════════════════════════════════════════════════════
#  순수 함수 API
# ══════════════════════════════════════════════════════════════════
def clamp_week(week) -> int:
    """1..WEEKS_TOTAL 로 clamp. 비정상 입력도 절대 예외를 내지 않는다."""
    try:
        w = int(week)
    except (TypeError, ValueError):
        return 1
    return max(1, min(WEEKS_TOTAL, w))


def phase_of(week: int) -> str:
    w = clamp_week(week)
    for name, lo, hi in PHASES:
        if lo <= w <= hi:
            return name
    return PHASES[-1][0]


def week_meta(week: int) -> Dict:
    """주차 메타(theme/goal_days/support/unlock/mission) — 항상 dict 반환."""
    return dict(_WEEK_BY_NO[clamp_week(week)])


def goal_days(week: int) -> int:
    return int(week_meta(week)["goal_days"])


def normalize_track(track: Optional[str]) -> str:
    return track if track in TRACKS else "diet"


def band_cap(band: Optional[str], week: int) -> int:
    """보조 항목 상한 = 밴드 캡 × 주차 진행(스펙 B-4/C10).

    안정: 1~2주 0 → 3~6주 1 → 7~12주 2
    주의: 최대 1
    경고: 0 (12주 내내 메인 1개)
    """
    w = clamp_week(week)
    if band == "경고":
        return 0
    week_cap = int(_WEEK_BY_NO[w]["support"])
    band_max = 1 if band == "주의" else 2
    return max(0, min(week_cap, band_max))


def banner_for(track: str, band: Optional[str]) -> Optional[str]:
    return _BANNER.get(normalize_track(track), {}).get(band or "")


def today_action(week: int, track: str) -> Dict:
    """주차·트랙 → 오늘의 메인 행동(기록형). 항상 유효한 dict."""
    w = clamp_week(week)
    t = normalize_track(track)
    a = ROUTINE_ACTIONS.get((w, t)) or ROUTINE_ACTIONS[(1, "diet")]
    return dict(a)


def ask_chips(week: int) -> List[str]:
    return list(ASK_CHIPS.get(clamp_week(week), []))


def support_items(pool: Optional[List[Dict]], week: int, band: Optional[str]) -> List[Dict]:
    """보조 행동 선택(스펙 B-3) — coaching_engine 이 만든 풀에서 주차별 순환.

    풀이 비면 빈 배열(프론트가 섹션 자체를 렌더하지 않음).
    """
    cap = band_cap(band, week)
    if cap <= 0 or not pool:
        return []
    items = [x for x in pool if isinstance(x, dict) and x.get("text")]
    if not items:
        return []
    w = clamp_week(week)
    start = (w - 1) % len(items)          # 주차마다 시작점을 밀어 순환(중복 체감 감소)
    picked = [items[(start + i) % len(items)] for i in range(min(cap, len(items)))]
    return [{"key": p.get("key"), "text": p.get("text"), "cite": p.get("cite")} for p in picked]


def week_preview(band: Optional[str] = None) -> List[Dict]:
    """12주 전체 미리보기(온보딩·프로그램 탭용)."""
    out = []
    for m in WEEKS:
        out.append({
            "w": m["w"], "phase": phase_of(m["w"]), "theme": m["theme"],
            "goal_days": m["goal_days"], "mission": m["mission"],
            "unlock": m["unlock"], "item_cap": band_cap(band, m["w"]),
        })
    return out


def transition(done_days: int, goal: int, band: Optional[str] = None) -> str:
    """주차 전환 판정(스펙 C9: 70/40). 경고 밴드는 advance 금지."""
    try:
        g = max(1, int(goal))
        d = max(0, int(done_days))
    except (TypeError, ValueError):
        return "hold"
    ratio = d / g
    if ratio >= 0.7:
        return "hold" if band == "경고" else "advance"
    if ratio < 0.4:
        return "simplify"
    return "hold"


def compliance_check(texts: List[str], band: Optional[str] = None) -> Dict:
    """WC-C 백스톱(defense-in-depth). 커리큘럼은 결정적이라 정상 통과가 기대값."""
    scan = " ".join(t for t in texts if t)
    try:
        return _cc.check_plan(scan, band)
    except Exception:
        return {"ok": True, "action": "pass", "violations": []}


def generate_program(track: str, intake: Optional[Dict] = None,
                     band: Optional[str] = None, focus: Optional[str] = None,
                     anchor: Optional[str] = None) -> Dict:
    """프로그램 생성(스펙 E-4). 보조 항목 풀은 coaching_engine.generate_plan() 재사용.

    반환: {track, focus, anchor, band, banner, item_cap, weeks, plan_items,
           today, compliance_action, curriculum_version}
    """
    t = normalize_track(track)
    intake = intake or {}

    plan_items: List[Dict] = []
    plan_banner = None
    plan_action = "pass"
    try:
        import coaching_engine as _ce
        plan = _ce.generate_plan(t, intake, band=band)
        plan_items = plan.get("items") or []
        plan_banner = plan.get("banner")
        plan_action = plan.get("compliance_action", "pass")
    except Exception:
        plan_items = []          # 보조 풀 없이도 메인 행동만으로 동작(비차단)

    main = today_action(1, t)
    banner = banner_for(t, band) or plan_banner

    chk = compliance_check([main["text"]] + [i.get("text", "") for i in plan_items], band)
    action = chk.get("action", "pass")
    if not chk.get("ok"):
        plan_items = []          # 위반 시 보조 전면 제거 — 메인(결정적 기록행동)만 남긴다
        action = "fallback_" + action

    return {
        "track": t, "focus": focus, "anchor": anchor, "band": band,
        "banner": banner,
        "item_cap": band_cap(band, 1),
        "weeks": week_preview(band),
        "plan_items": plan_items,
        "today": main,
        "compliance_action": action,
        "curriculum_version": CURRICULUM_VERSION,
    }
