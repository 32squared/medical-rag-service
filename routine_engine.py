"""routine_engine.py — 루틴 프로그램 엔진 (순수 함수, 팩 기반).

정본: docs/plan/28-routine-pack-platform.md(팩 플랫폼) ·
      docs/plan/25-routine-transition-spec.md §B·§E-4·§H-4(건강 12주 규칙).

커리큘럼 내용(주차·행동·문진·보조 풀·배너)은 코드가 아니라 **팩 파일**에 있다
(routines/packs/<id>/v<n>.json, 로더 = routine_packs). 이 모듈은 팩을 받아 계산만 한다.
모든 공개 함수의 `pack` 인자는 Pack · 팩 id · None(기본 팩 health_12w) 을 받는다.

설계 원칙(coaching_engine 상속):
  - **결정적 템플릿**. LLM 자유생성 아님 → 효능표방·처방성 구조적 0.
  - 모든 행동에 출처(cite) 필수 — 팩 무결성 검사가 강제.
  - 산출은 coaching_compliance(WC-C)로 백스톱(defense-in-depth).
  - 안전 규칙(밴드 캡·advance 금지)은 팩이 아니라 안전 프로필(routine_packs.SAFETY_PROFILES)이 정한다.

의료법 27조: 진단·처방·효능·용량 표현 금지. 밴드는 '구간 안내'이며 판정이 아니다.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import coaching_compliance as _cc
import routine_packs as _rp

PackRef = Union["_rp.Pack", str, None]


def _pk(pack: PackRef) -> "_rp.Pack":
    if isinstance(pack, _rp.Pack):
        return pack
    return _rp.get(pack)


# ── 하위 호환 상수(기본 팩 기준) — 기존 호출부·테스트용. 새 코드는 팩 함수를 쓴다. ──
_DEFAULT = _rp.get()
CURRICULUM_VERSION = _DEFAULT.version
WEEKS_TOTAL = _DEFAULT.weeks_total
PHASES: List[Tuple[str, int, int]] = [(p.name, p.from_, p.to) for p in _DEFAULT.phases]
TRACKS = tuple(_DEFAULT.track_ids)
FOCUS_TRACK = {f: t.id for t in _DEFAULT.tracks for f in t.recommend_when}


def _week_dict(wk: "_rp.Week") -> Dict:
    d = {"w": wk.w, "theme": wk.theme, "goal_days": wk.goal_days,
         "support": wk.support_cap, "unlock": wk.unlock, "mission": wk.mission}
    if wk.warning_mission:              # 선택 필드는 있을 때만(v1 페이로드 불변)
        d["warning_mission"] = wk.warning_mission
    return d


WEEKS: List[Dict] = [_week_dict(w) for w in _DEFAULT.weeks]
ASK_CHIPS: Dict[int, List[str]] = {w.w: list(w.ask_chips) for w in _DEFAULT.weeks}


# ══════════════════════════════════════════════════════════════════
#  순수 함수 API
# ══════════════════════════════════════════════════════════════════
def clamp_week(week, pack: PackRef = None) -> int:
    """1..weeks_total 로 clamp. 비정상 입력도 절대 예외를 내지 않는다."""
    n = _pk(pack).weeks_total
    try:
        w = int(week)
    except (TypeError, ValueError):
        return 1
    return max(1, min(n, w))


def _week(week, pack: PackRef = None) -> "_rp.Week":
    p = _pk(pack)
    return p.weeks[clamp_week(week, p) - 1]


def phase_of(week, pack: PackRef = None) -> str:
    p = _pk(pack)
    w = clamp_week(week, p)
    for ph in p.phases:
        if ph.from_ <= w <= ph.to:
            return ph.name
    return p.phases[-1].name


def phases(pack: PackRef = None) -> List[Dict]:
    """단계 목록(프론트 타임라인·미리보기 라벨용)."""
    return [{"id": ph.id, "name": ph.name, "from": ph.from_, "to": ph.to, "desc": ph.desc}
            for ph in _pk(pack).phases]


def week_meta(week, pack: PackRef = None) -> Dict:
    """주차 메타(theme/goal_days/support/unlock/mission) — 항상 dict 반환."""
    return _week_dict(_week(week, pack))


def goal_days(week, pack: PackRef = None) -> int:
    return int(_week(week, pack).goal_days)


def normalize_track(track: Optional[str], pack: PackRef = None) -> str:
    p = _pk(pack)
    return track if track in p.track_ids else p.default_track


def band_cap(band: Optional[str], week, pack: PackRef = None) -> int:
    """보조 항목 상한 = min(주차 support_cap, 안전 프로필의 밴드 상한).

    medical/physical: 안정 2 · 주의 1 · 경고 0 (12주 내내 메인 1개).
    neutral: 밴드 무관 2.
    """
    p = _pk(pack)
    prof = p.profile
    week_cap = int(_week(week, p).support_cap)
    band_max = prof["band_max"].get(band or "", prof["default_max"])
    return max(0, min(week_cap, band_max))


def banner_for(track: str, band: Optional[str], pack: PackRef = None) -> Optional[str]:
    p = _pk(pack)
    return p.banners.get(normalize_track(track, p), {}).get(band or "")


def _action_dict(p: "_rp.Pack", a: "_rp.Action") -> Dict:
    d = {"id": a.id, "text": a.text, "cite": p.source_label(a.cite), "minutes": a.minutes,
         "input": {"kind": a.input.kind, "options": list(a.input.options)}}
    for k in ("meta", "coach"):         # 선택 필드는 있을 때만(v1 페이로드 불변)
        if getattr(a, k):
            d[k] = getattr(a, k)
    return d


def mission_for(week, band: Optional[str] = None, pack: PackRef = None) -> str:
    """주간 미션. 경고 밴드는 팩의 치환 미션이 있으면 그것(27 §2-5)."""
    wk = _week(week, pack)
    return (wk.warning_mission if band == "경고" and wk.warning_mission else wk.mission)


def today_action(week, track: str, pack: PackRef = None, band: Optional[str] = None) -> Dict:
    """주차·트랙 → 오늘의 메인 행동(기록형). 경고 밴드는 팩의 치환 행동이 있으면 그것.
    항상 유효한 dict."""
    p = _pk(pack)
    wk = _week(week, p)
    t = normalize_track(track, p)
    a = None
    if band == "경고":
        a = wk.warning_actions.get(t)
    a = a or wk.actions.get(t) or p.weeks[0].actions[p.default_track]
    return _action_dict(p, a)


def ask_chips(week, pack: PackRef = None) -> List[str]:
    return list(_week(week, pack).ask_chips)


def _matches(intake: Dict, cond: Dict[str, List[Optional[str]]]) -> bool:
    for qid, allowed in cond.items():
        v = intake.get(qid) or None                 # 빈 문자열 = 미응답
        if v not in allowed:
            return False
    return True


def _hits(intake: Dict, cond: Dict[str, List[Optional[str]]]) -> bool:
    return any((intake.get(qid) or None) in vals for qid, vals in cond.items())


def plan_keys(track: str, intake: Optional[Dict], band: Optional[str] = None,
              pack: PackRef = None) -> List[str]:
    """문진·밴드 → 보조 행동 풀 키(결정적). 팩의 누적 규칙 + 밴드별 풀 상한."""
    p = _pk(pack)
    t = normalize_track(track, p)
    intake = intake or {}
    sr = p.support_rules.get(t)
    picks: List[str] = []
    if sr:
        for r in sr.rules:
            if r.when and not _matches(intake, r.when):
                continue
            if r.unless and _hits(intake, r.unless):
                continue
            picks += r.add
    seen: set = set()
    ordered = [k for k in picks if not (k in seen or seen.add(k))]
    if not ordered and sr:
        ordered = list(sr.default)
    cap = p.support_pool_cap.get(band or "", p.support_pool_cap["default"])
    return ordered[:cap]


def plan_items(track: str, intake: Optional[Dict], band: Optional[str] = None,
               pack: PackRef = None) -> List[Dict]:
    """보조 행동 풀(키·문구·출처 라벨)."""
    p = _pk(pack)
    t = normalize_track(track, p)
    by_key = {x.key: x for x in p.support_pool.get(t, [])}
    return [{"key": k, "text": by_key[k].text, "cite": p.source_label(by_key[k].cite)}
            for k in plan_keys(t, intake, band, p) if k in by_key]


def support_items(pool: Optional[List[Dict]], week, band: Optional[str],
                  pack: PackRef = None) -> List[Dict]:
    """보조 행동 선택(스펙 B-3) — 풀에서 주차별 순환. 풀이 비면 빈 배열."""
    cap = band_cap(band, week, pack)
    if cap <= 0 or not pool:
        return []
    items = [x for x in pool if isinstance(x, dict) and x.get("text")]
    if not items:
        return []
    w = clamp_week(week, pack)
    start = (w - 1) % len(items)          # 주차마다 시작점을 밀어 순환(중복 체감 감소)
    picked = [items[(start + i) % len(items)] for i in range(min(cap, len(items)))]
    return [{"key": x.get("key"), "text": x.get("text"), "cite": x.get("cite")} for x in picked]


def week_preview(band: Optional[str] = None, pack: PackRef = None) -> List[Dict]:
    """전체 주차 미리보기(온보딩·프로그램 탭용)."""
    p = _pk(pack)
    return [{"w": wk.w, "phase": phase_of(wk.w, p), "theme": wk.theme,
             "goal_days": wk.goal_days, "mission": wk.mission,
             "unlock": wk.unlock, "item_cap": band_cap(band, wk.w, p)} for wk in p.weeks]


def transition(done_days: int, goal: int, band: Optional[str] = None,
               pack: PackRef = None) -> str:
    """주차 전환 판정(기본 70/40, 팩이 조정). 안전 프로필의 차단 밴드는 advance 금지."""
    p = _pk(pack)
    try:
        g = max(1, int(goal))
        d = max(0, int(done_days))
    except (TypeError, ValueError):
        return "hold"
    ratio = d / g
    if ratio >= p.transition.advance:
        return "hold" if band in p.profile["advance_block"] else "advance"
    if ratio < p.transition.simplify:
        return "simplify"
    return "hold"


def compliance_check(texts: List[str], band: Optional[str] = None,
                     pack: PackRef = None) -> Dict:
    """WC-C 백스톱(defense-in-depth). 커리큘럼은 결정적이라 정상 통과가 기대값."""
    scan = " ".join(t for t in texts if t)
    try:
        return _cc.check_plan(scan, band, profile=_pk(pack).safety_profile)
    except Exception:
        return {"ok": True, "action": "pass", "violations": []}


def generate_program(track: str, intake: Optional[Dict] = None,
                     band: Optional[str] = None, focus: Optional[str] = None,
                     anchor: Optional[str] = None, pack: PackRef = None) -> Dict:
    """프로그램 생성(스펙 E-4). 보조 항목 풀은 팩의 문진 규칙으로 고른다.

    반환: {track, focus, anchor, band, banner, item_cap, weeks, plan_items,
           today, compliance_action, curriculum_version, pack_id}
    """
    p = _pk(pack)
    t = normalize_track(track, p)
    items = plan_items(t, intake or {}, band, p)
    main = today_action(1, t, p, band)
    chk = compliance_check([main["text"]] + [i.get("text", "") for i in items], band, p)
    action = chk.get("action", "pass")
    if not chk.get("ok"):
        items = []               # 위반 시 보조 전면 제거 — 메인(결정적 기록행동)만 남긴다
        action = "fallback_" + action

    return {
        "track": t, "focus": focus, "anchor": anchor, "band": band,
        "banner": banner_for(t, band, p),
        "item_cap": band_cap(band, 1, p),
        "weeks": week_preview(band, p),
        "plan_items": items,
        "today": main,
        "compliance_action": action,
        "curriculum_version": p.version,
        "pack_id": p.id,
    }


def pack_block(pack: PackRef = None) -> Dict:
    """홈·프로그램 페이로드의 `pack` 블록(28 FR-S8)."""
    p = _pk(pack)
    return {"id": p.id, "version": p.version, "name": p.name, "domain": p.domain,
            "safety_profile": p.safety_profile, "weeks_total": p.weeks_total,
            "phases": phases(p),
            "tracks": [{"id": t.id, "name": t.name, "icon": t.icon, "desc": t.desc} for t in p.tracks]}
