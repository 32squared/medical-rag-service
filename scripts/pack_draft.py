"""pack_draft.py — 브리프 → LLM 초안 팩(28 D8 · FR-T5). **초안 전용.**

    python scripts/pack_draft.py routines/briefs/running_8w.json
    python scripts/pack_draft.py routines/briefs/running_8w.json --rounds 4 --effort low

원칙
- 구조(주차 수·단계·id·보조 캡)는 pack_new 스캐폴드가 결정적으로 만든다. LLM 은 **문구만** 채운다.
- 출처는 브리프에 사람이 적는다. LLM 은 그 key 중에서만 고른다(출처 창작 0).
- 조립 → 모델 검증 → lint → 걸린 주차만 오류 메시지와 함께 다시 쓰게 한다(최대 --rounds 회).
- 결과는 routines/drafts/<id>/v1.json 과 검수 메모(review.md)에만 쓴다. 레지스트리(routines/packs)는
  건드리지 않는다. 사람이 읽고 고친 뒤 packs/ 로 옮기고 pack_lint 를 통과시켜 PR 을 올린다.

브리프(JSON)
    {"id": "running_8w", "name": "달리기 입문 8주", "domain": "sport", "safety_profile": "physical",
     "weeks": 8, "audience": "운동 습관이 없는 30~40대 직장인", "goal": "...", "notes": "...",
     "tracks": [{"id": "outdoor", "name": "밖에서 달리기", "icon": "run"}, ...],
     "sources": [{"key": "kspo", "label": "국민체육진흥공단 국민체력100", "url": "https://nfa.kspo.or.kr"}]}
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import re
import sys
from typing import Callable, Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import routine_packs as rp  # noqa: E402
import pack_new  # noqa: E402

DRAFTS_DIR = ROOT / "routines" / "drafts"
CHUNK = 6                                    # 한 번에 쓰게 할 주차 수
LLM = Callable[[str, str], str]              # (system, user) -> 응답 텍스트

_SLUG = re.compile(r"[^a-z0-9_]+")
_WEEK_PATH = re.compile(r"^weeks\[(\d+)\]")


class BriefError(ValueError):
    """사람이 브리프를 고쳐야 하는 문제(LLM 이 풀 수 없음)."""


# ══════════════════════════ 브리프 ══════════════════════════
def load_brief(src) -> Dict:
    b = json.loads(pathlib.Path(src).read_text(encoding="utf-8")) if not isinstance(src, dict) else dict(src)
    miss = [k for k in ("id", "name", "domain", "safety_profile", "weeks", "tracks", "sources") if not b.get(k)]
    if miss:
        raise BriefError(f"브리프 필수 항목 없음: {miss}")
    if b["safety_profile"] not in rp.SAFETY_PROFILES:
        raise BriefError(f"safety_profile 은 {sorted(rp.SAFETY_PROFILES)} 중 하나")
    for t in b["tracks"]:
        if t.get("icon", "star") not in rp.ICONS:
            raise BriefError(f"트랙 {t.get('id')} 아이콘 '{t.get('icon')}' — 허용: {sorted(rp.ICONS)}")
    if b["safety_profile"] == "medical":
        bad = [s["label"] for s in b["sources"] if not rp._MEDICAL_SOURCES.search(s.get("label", ""))]
        if bad:
            raise BriefError(f"medical 팩 출처는 공신력 보건 기관만(L6): {bad}")
    return b


def base_pack(b: Dict) -> Dict:
    """스캐폴드(구조 확정) + 브리프의 이름·트랙·출처."""
    tids = [t["id"] for t in b["tracks"]]
    pk = pack_new.scaffold(b["id"], int(b["weeks"]), tids, b["safety_profile"], b["domain"], b["name"])
    pk["tracks"] = [{"id": t["id"], "name": t.get("name", "TODO"), "icon": t.get("icon", "star"),
                     "desc": "TODO", "target_noun": ""} for t in b["tracks"]]
    pk["sources"] = [{"key": s["key"], "label": s["label"], "url": s.get("url")} for s in b["sources"]]
    for w in pk["weeks"]:
        for acts in (w["actions"], w.get("warning_actions", {})):
            for a in acts.values():
                a["cite"] = pk["sources"][0]["key"]
    if b["safety_profile"] == "physical":
        pk["support_pool_cap"] = {"default": 4, "경고": 2}
    return pk


# ══════════════════════════ 프롬프트 ══════════════════════════
_PROFILE_RULE = {
    "medical": "건강 관리 루틴. 효능·치료·예방 효과를 말하지 않는다. 진료를 대신한다는 인상을 주지 않는다.",
    "physical": ("몸을 쓰는 루틴. 통증·부상이 있을 때 무엇을 하라고 지시하지 않는다"
                 "(통증은 항상 '쉬기·해당없음'으로만). 강도는 천천히 올린다."),
    "neutral": "학습·취미 루틴. 합격·기간 내 달성 같은 성과를 약속하지 않는다.",
}


def system_prompt(profile: str) -> str:
    budget = ", ".join(f"{k} {v}자" for k, v in rp.BUDGET.items())
    return f"""너는 한국어 습관 루틴 커리큘럼 작가다. 사람이 검수할 **초안**을 JSON 으로만 쓴다(설명·코드펜스 금지).

[안전 프로필] {profile} — {_PROFILE_RULE[profile]}

[반드시 지킬 것]
1. 글자수 상한(공백 포함): {budget}. 넘으면 버려진다. 짧게 쓴다.
2. 해요체. 이모지·특수 기호 장식 금지.
3. 미실천을 규정하는 말 금지: 실패, 미달, 놓친/놓쳤, 결석, 또 못, 게으름, 벌칙, 낙오, 포기했.
4. 효과·결과 약속 금지: 낫는다, 치료, 완치, 예방 효과, 효과가 있어요, "N개월이면 ~ 합격/완성/달성".
5. 오늘 할 것은 트랙당 1개. "하고 남기는" 행동(마지막에 탭/골라 탭). 가능하면 언제 할지(앵커)를 넣는다.
6. 입력: tap(옵션 []), choice(보기 2~5개, 각 12자 이내), scale(단계 라벨 3~5개). 숫자·자유 입력 없음.
7. cite 는 주어진 출처 key 중에서만, 그 행동을 실제로 뒷받침하는 출처를 고른다.
8. 질문칩은 정확히 3개, 각 24자 이내. **사용자가 코치에게 묻는 질문**이다(예: "빈 스윙은 왜 먼저 하나요?",
   "뻐근한 날도 해도 되나요?"). 앱이 사용자에게 묻는 말("느낌 어땠나요?", "언제 했나요?")은 쓰지 않는다.
9. 행동의 절반 이상은 choice·scale 로 오늘의 느낌·양·상황을 고르게 한다
   (예: "7번 아이언 20구, 잘 맞은 비율 탭" → choice ["절반 이상", "몇 개", "거의 없음"]).
   tap 은 첫 주·다시 잇는 주·유지 확정 주처럼 "했다" 자체가 기록인 주에 쓴다.
   "해당없음"은 화면에 따로 있으니 보기로 넣지 않는다.

[커리큘럼 원칙]
P1 하루 한 가지, 하고 남기기 / P2 정착기엔 더하지 않고 첫 주는 쉽게 / P3 정착→쌓기→써먹기→유지 흐름,
마지막은 '적게 남기기'(유지 루틴 확정) / P4 이미 하는 일 뒤에 붙이기 / P5 무너진 날 다시 잇는 주차를
써먹기 단계 안에 둔다(tap 행동) / P6 출처 / P7 성과 약속 금지 / P8 주마다 질문칩 3개."""


def _brief_block(b: Dict, base: Dict) -> str:
    tracks = "\n".join(f"- {t['id']}: {t['name']}" + (f" — {t.get('hint')}" if t.get("hint") else "")
                       for t in b["tracks"])
    srcs = "\n".join(f"- {s['key']}: {s['label']}" for s in base["sources"])
    phases = "\n".join(f"- {p['id']} {p['name']}: {p['from']}~{p['to']}주" for p in base["phases"])
    return (f"루틴: {b['name']} ({b['weeks']}주, 분야 {b['domain']})\n"
            f"대상: {b.get('audience', '')}\n목표: {b.get('goal', '')}\n메모: {b.get('notes', '')}\n"
            f"트랙:\n{tracks}\n단계:\n{phases}\n출처 key:\n{srcs}")


def skeleton_prompt(b: Dict, base: Dict, feedback: List[str]) -> str:
    tids = [t["id"] for t in b["tracks"]]
    need_banner = b["safety_profile"] in ("medical", "physical")
    fb = ("\n[지난 초안에서 고칠 점]\n- " + "\n- ".join(feedback)) if feedback else ""
    return f"""{_brief_block(b, base)}
REQUEST: skeleton
아래 JSON 을 채워라(키 이름 그대로).
{{
 "tagline": "30자 이내 한 줄",
 "tracks": {{{", ".join(f'"{t}": {{"desc": "40자 이내", "target_noun": "기록 대상 명사"}}' for t in tids)}}},
 "phases": {{{", ".join(f'"{p["id"]}": {{"desc": "30자 이내"}}' for p in base["phases"])}}},
 "intake": {{"<트랙id>": [{{"id": "영문소문자", "q": "24자 이내 질문", "why": "20자 이내",
             "options": [{{"label": "16자 이내", "value": "영문소문자"}}]}}]}},
 "support_pool": {{"<트랙id>": [{{"key": "영문소문자", "text": "30자 이내 보조 행동", "cite": "출처key", "tags": []}}]}},
 "support_rules": {{"<트랙id>": {{"rules": [{{"when": {{"문항id": ["value"]}}, "add": ["key"]}}], "default": ["key"]}}}}{',' if need_banner else ''}
 {'"banners": {"<트랙id>": {"주의": "80자 이내", "경고": "80자 이내 — 먼저 의료진과 상담 안내"}}' if need_banner else ''}
}}
- 트랙마다 문진 3개: 수준, 언제 할지(id "anchor"), 트랙에 맞는 하나. 보기 2~4개.
- banners 는 사용자의 **건강 측정값**(혈압 등)이 주의·경고 구간일 때 행동 카드 위에 뜬다. 질환명을 늘어놓지 않는다.
  주의: "측정값이 주의 구간이에요."로 시작 — 강도는 가볍게, 불편한 날은 쉬기.
  경고: "측정값이 경고 구간이에요."로 시작 — 이 활동 전에 의료진과 먼저 상담, 지금은 몸 상태 기록만.
- 보조 행동 풀은 트랙마다 4~5개, 규칙은 문진 value 로 고른다.{fb}"""


def weeks_prompt(b: Dict, base: Dict, wks: List[int], feedback: Dict[int, List[str]]) -> str:
    tids = [t["id"] for t in b["tracks"]]
    warn = b["safety_profile"] in ("medical", "physical")
    phase_of = {w: p["name"] for p in base["phases"] for w in range(p["from"], p["to"] + 1)}
    done = [f"{w['w']}주 {w['theme']}" for w in base["weeks"] if w["theme"] != "TODO" and w["w"] not in wks]
    rows = "\n".join(f"- {w}주: 단계 {phase_of[w]}, 보조 캡 {base['weeks'][w - 1]['support_cap']}" for w in wks)
    fb = ""
    if feedback:
        fb = "\n[지난 초안에서 고칠 점 — 해당 주차를 새로 쓴다]\n" + "\n".join(
            f"- {w}주: " + " / ".join(m) for w, m in sorted(feedback.items()))
    act = '{"slug": "영문소문자", "text": "30자 이내", "cite": "출처key", "minutes": 10, "input": {"kind": "tap", "options": []}}'
    warn_line = (f',\n   "warning_actions": {{{", ".join(f"{chr(34)}{t}{chr(34)}: {act}" for t in tids)}}}'
                 if warn else "")
    warn_rule = ("\n- warning_actions: 건강 경고 구간일 때 대신 할 가장 가벼운 기록"
                 + (" — 통증 얘기가 아니라 측정값 경고 때의 대체 행동. 예: \"달리기는 쉬고 오늘 몸 상태만 탭\""
                    " choice [\"가뿐\", \"보통\", \"불편\"]." if b["safety_profile"] == "physical" else ".")
                 if warn else "")
    return f"""{_brief_block(b, base)}
이미 쓴 주차: {", ".join(done) or "없음"}
REQUEST_WEEKS: {json.dumps(wks)}
{rows}
아래 형식으로 요청한 주차만 JSON 으로 써라.
{{"weeks": [
  {{"w": 1, "theme": "20자 이내", "mission": "40자 이내 — 7일 중 N일 …", "goal_days": 3,
   "actions": {{{", ".join(f"{chr(34)}{t}{chr(34)}: {act}" for t in tids)}}}{warn_line},
   "ask_chips": ["24자 이내", "24자 이내", "24자 이내"]}}
]}}
- goal_days 1~7, 1주차는 3 이하. 주제가 앞 주차와 겹치지 않게 조금씩 나아간다.{warn_rule}{fb}"""


# ══════════════════════════ 조립 ══════════════════════════
def _json_from(text: str) -> Dict:
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("JSON 없음")
    return json.loads(s[i:j + 1])


def _slug(v, fallback: str) -> str:
    s = _SLUG.sub("_", str(v or "").lower()).strip("_")
    s = s if re.match(r"^[a-z]", s or "") else f"x_{s}" if s else fallback
    return s[:40] if len(s) >= 2 else fallback


def _action(raw: Dict, wid: str, srcs: set, path: str, issues: List[str]) -> Dict:
    raw = raw if isinstance(raw, dict) else {}
    inp = raw.get("input") if isinstance(raw.get("input"), dict) else {}
    kind = inp.get("kind") if inp.get("kind") in ("tap", "choice", "scale") else "tap"
    opts = [str(o) for o in (inp.get("options") or []) if str(o).strip()] if kind != "tap" else []
    if kind != "tap" and len(opts) < 2:
        issues.append(f"{path}.input: {kind} 은 보기 2개 이상")
        kind, opts = "tap", []
    cite = str(raw.get("cite", ""))
    if cite not in srcs:
        issues.append(f"{path}.cite: '{cite}' 는 주어진 출처 key 가 아님")
        cite = sorted(srcs)[0]
    try:
        minutes = max(1, min(60, int(raw.get("minutes", 5))))
    except (TypeError, ValueError):
        minutes = 5
    return {"id": wid, "text": str(raw.get("text", "")).strip() or "TODO", "cite": cite,
            "minutes": minutes, "input": {"kind": kind, "options": opts}}


def merge_skeleton(pk: Dict, sk: Dict) -> List[str]:
    """스켈레톤 응답을 pk 에 반영. 고칠 점(문자열)을 돌려준다."""
    issues: List[str] = []
    srcs = {s["key"] for s in pk["sources"]}
    tids = [t["id"] for t in pk["tracks"]]
    pk["tagline"] = str(sk.get("tagline", "")).strip() or "TODO"
    for t in pk["tracks"]:
        x = (sk.get("tracks") or {}).get(t["id"]) or {}
        t["desc"] = str(x.get("desc", "")).strip() or "TODO"
        t["target_noun"] = str(x.get("target_noun", "")).strip()
    for p in pk["phases"]:
        p["desc"] = str(((sk.get("phases") or {}).get(p["id"]) or {}).get("desc", "")).strip() or "TODO"

    pk["intake"] = {}
    for t in tids:
        qs, seen = [], set()
        for i, q in enumerate((sk.get("intake") or {}).get(t) or []):
            qid = _slug(q.get("id"), f"q{i + 1}")
            if qid in seen:
                continue
            seen.add(qid)
            opts = [{"label": str(o.get("label", "")).strip(), "value": _slug(o.get("value"), f"v{j + 1}")}
                    for j, o in enumerate(q.get("options") or []) if isinstance(o, dict) and o.get("label")]
            if len(opts) < 2:
                issues.append(f"intake.{t}.{qid}: 보기 2개 이상")
                continue
            qs.append({"id": qid, "q": str(q.get("q", "")).strip() or "TODO",
                       "why": (str(q.get("why")).strip() or None) if q.get("why") else None, "options": opts})
        pk["intake"][t] = qs

    pk["support_pool"] = {}
    for t in tids:
        pool, seen = [], set()
        for i, x in enumerate((sk.get("support_pool") or {}).get(t) or []):
            key = _slug(x.get("key"), f"s{i + 1}")
            if key in seen or not x.get("text"):
                continue
            seen.add(key)
            cite = str(x.get("cite", ""))
            if cite not in srcs:
                issues.append(f"support_pool.{t}.{key}.cite: '{cite}' 는 주어진 출처 key 가 아님")
                cite = sorted(srcs)[0]
            pool.append({"key": key, "text": str(x["text"]).strip(), "cite": cite,
                         "tags": [str(g) for g in (x.get("tags") or [])][:4]})
        pk["support_pool"][t] = pool

    pk["support_rules"] = {}                     # 없는 key·문항 참조는 결정적으로 버린다
    for t in tids:
        keys = {x["key"] for x in pk["support_pool"][t]}
        qvals = {q["id"]: {o["value"] for o in q["options"]} for q in pk["intake"][t]}
        raw = (sk.get("support_rules") or {}).get(t) or {}
        rules = []
        for r in raw.get("rules") or []:
            add = [k for k in (_slug(k, "") for k in r.get("add") or []) if k in keys]
            cond = {}
            for part in ("when", "unless"):
                c = {}
                for qid, vals in (r.get(part) or {}).items():
                    qid = _slug(qid, "")
                    if qid in qvals:
                        vs = [v for v in (None if v is None else _slug(v, "") for v in (vals or [])) if v is None or v in qvals[qid]]
                        if vs:
                            c[qid] = vs
                cond[part] = c
            if add:
                rules.append({"when": cond["when"], "unless": cond["unless"], "add": add})
        default = [k for k in (_slug(k, "") for k in raw.get("default") or []) if k in keys]
        pk["support_rules"][t] = {"rules": rules, "default": default or sorted(keys)[:1]}

    if pk["safety_profile"] in ("medical", "physical"):
        pk["banners"] = {}
        for t in tids:
            bb = (sk.get("banners") or {}).get(t) or {}
            pk["banners"][t] = {band: str(bb.get(band, "")).strip() or "TODO" for band in ("주의", "경고")}
    return issues


def merge_weeks(pk: Dict, resp: Dict, wks: List[int]) -> Dict[int, List[str]]:
    issues: Dict[int, List[str]] = {}
    srcs = {s["key"] for s in pk["sources"]}
    tids = [t["id"] for t in pk["tracks"]]
    got = {int(w.get("w", 0)): w for w in (resp.get("weeks") or []) if isinstance(w, dict)}
    for n in wks:
        iss: List[str] = []
        w, raw = pk["weeks"][n - 1], got.get(n)
        if not raw:
            issues[n] = ["응답에 이 주차가 없음"]
            continue
        w["theme"] = str(raw.get("theme", "")).strip() or "TODO"
        w["mission"] = str(raw.get("mission", "")).strip() or "TODO"
        try:
            g = max(1, min(7, int(raw.get("goal_days", w["goal_days"]))))
        except (TypeError, ValueError):
            g = w["goal_days"]
        w["goal_days"] = min(g, 3) if n == 1 else g
        for t in tids:
            a = (raw.get("actions") or {}).get(t)
            if not a:
                iss.append(f"actions.{t} 없음")
            w["actions"][t] = _action(a, f"w{n}:{t}:{_slug((a or {}).get('slug'), 'act')}", srcs,
                                      f"weeks[{n}].actions.{t}", iss)
        if "warning_actions" in w:
            for t in tids:
                a = (raw.get("warning_actions") or {}).get(t)
                if not a:
                    iss.append(f"warning_actions.{t} 없음")
                w["warning_actions"][t] = _action(a, f"w{n}:{t}:warn", srcs, f"weeks[{n}].warning_actions.{t}", iss)
        chips = [str(c).strip() for c in (raw.get("ask_chips") or []) if str(c).strip()]
        w["ask_chips"] = chips[:3] if len(chips) >= 3 else chips + ["TODO"] * (3 - len(chips))
        if iss:
            issues[n] = iss
    return issues


_CHIP_BACKWARD = re.compile(r"(어땠나요|어땠어요|했나요|었나요|았나요|됐나요|였나요)\s*\??$")
_PAIN = re.compile(r"(통증|아프|아플|부상)")


def quality_issues(pk: Dict, first: bool):
    """lint 밖의 초안 버릇(질문칩 방향·배너 첫 문장·경고 치환의 통증 언급·해당없음 보기·tap 쏠림·복구 주차).
    first=True 일 때만 권고성 항목(tap 쏠림·복구 주차)을 되돌린다 — 끝없이 돌지 않게."""
    sk: List[str] = []
    wk: Dict[int, List[str]] = {}
    for t, b in (pk.get("banners") or {}).items():
        for band in ("주의", "경고"):
            if not str(b.get(band, "")).startswith(f"측정값이 {band} 구간이에요"):
                sk.append(f"banners.{t}.{band}: '측정값이 {band} 구간이에요.'로 시작해야 함(질환 나열 금지)")
    for w in pk["weeks"]:
        n = w["w"]
        for i, c in enumerate(w["ask_chips"]):
            if _CHIP_BACKWARD.search(c):
                wk.setdefault(n, []).append(f"ask_chips[{i}] '{c}': 앱이 묻는 말 — 사용자가 코치에게 묻는 질문으로")
        for t, a in (w.get("warning_actions") or {}).items():
            if _PAIN.search(a["text"]):
                wk.setdefault(n, []).append(f"warning_actions.{t}: 통증이 아니라 측정값 경고 때의 대체 행동으로")
        for t, a in w["actions"].items():
            if "해당없음" in a["input"]["options"]:
                wk.setdefault(n, []).append(f"actions.{t}: '해당없음'은 화면에 따로 있음 — 보기에서 빼기")
    if first and len(pk["phases"]) >= 3:          # P5 — 써먹기 단계 가운데를 "다시 잇기" 주로
        use = pk["phases"][2]
        later = [w for w in pk["weeks"] if w["w"] >= use["from"]]
        for t in [x["id"] for x in pk["tracks"]]:
            if not any(w["actions"][t]["input"]["kind"] == "tap" for w in later):
                n = (use["from"] + use["to"]) // 2
                wk.setdefault(n, []).append(
                    f"actions.{t}: 이 주는 '거른 날 다시 잇기' 주 — 거른 다음 날은 아주 짧게 하고 탭(tap)")
    if first:
        for t in [x["id"] for x in pk["tracks"]]:
            taps = [w["w"] for w in pk["weeks"] if w["actions"][t]["input"]["kind"] == "tap"]
            if len(taps) / len(pk["weeks"]) > rp.TAP_SHARE_MAX:
                for n in taps[1:-1]:             # 첫 주·마지막 주 tap 은 그대로 둔다
                    wk.setdefault(n, []).append(f"actions.{t}: tap 대신 오늘의 느낌·양을 고르는 choice 로")
    return sk, wk


def lint_issues(pk: Dict):
    """(skeleton 고칠 점, {주차: 고칠 점}, 경고 목록) — error 만 되돌려 보낸다."""
    pack = rp.Pack.model_validate(pk)
    sk: List[str] = []
    wk: Dict[int, List[str]] = {}
    warns: List[str] = []
    for i in rp.lint(pack):
        line = f"{i['path']} [{i['rule']}] {i['msg']}"
        if i["level"] != "error":
            warns.append(line)
            continue
        m = _WEEK_PATH.match(i["path"])
        if m:
            wk.setdefault(int(m.group(1)), []).append(line)
        else:
            sk.append(line)
    return sk, wk, warns


# ══════════════════════════ LLM ══════════════════════════
def default_llm(effort: str = "low") -> LLM:
    """llm_router 의 기본 프로바이더(OpenAI). 배치 작업이라 추론 강도를 조금 올린다."""
    os.environ.setdefault("LLM_REASONING_EFFORT", effort)
    try:                                         # 사내망 TLS 가로채기 — OS 인증서 저장소를 쓴다(있을 때만)
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    import llm_router
    prov = llm_router.get_llm_provider()

    def call(system: str, user: str) -> str:
        for ev in prov.stream_chat(system=system, user=user, max_tokens=4096):
            if ev.get("type") == "ERROR":
                raise RuntimeError(ev.get("message"))
            if ev.get("type") == "STOP":
                return ev.get("text", "")
        raise RuntimeError("LLM 응답 없음")
    return call


def _ask(llm: LLM, system: str, user: str, tries: int = 2) -> Dict:
    last = None
    for _ in range(tries):
        try:
            return _json_from(llm(system, user))
        except (ValueError, json.JSONDecodeError) as e:
            last = e
    raise RuntimeError(f"LLM 이 JSON 을 주지 않음: {last}")


# ══════════════════════════ 파이프라인 ══════════════════════════
def draft(brief, llm: Optional[LLM] = None, rounds: int = 3, log=print) -> Dict:
    """초안 팩을 만든다. 반환: {"pack", "errors", "warnings", "rounds", "calls"}."""
    b = load_brief(brief)
    llm = llm or default_llm()
    pk = base_pack(b)
    sysp = system_prompt(b["safety_profile"])
    calls = 0

    def run_skeleton(fb):
        nonlocal calls
        calls += 1
        return merge_skeleton(pk, _ask(llm, sysp, skeleton_prompt(b, pk, fb)))

    def run_weeks(targets: List[int], fb: Dict[int, List[str]]):
        nonlocal calls
        out: Dict[int, List[str]] = {}
        for i in range(0, len(targets), CHUNK):
            part = targets[i:i + CHUNK]
            calls += 1
            log(f"  weeks {part[0]}~{part[-1]}")
            out.update(merge_weeks(pk, _ask(llm, sysp, weeks_prompt(b, pk, part, fb)), part))
        return out

    log(f"[draft] {b['id']} — skeleton")
    sk_fb = run_skeleton([])
    wk_fb = run_weeks(list(range(1, pk["weeks_total"] + 1)), {})
    done = 0
    for done in range(1, rounds + 1):
        sk_l, wk_l, _ = lint_issues(pk)
        sk_q, wk_q = quality_issues(pk, first=done == 1)   # 권고성 항목은 한 번만
        sk_fb = sk_fb + sk_l + sk_q
        for src in (wk_l, wk_q):
            for w, m in src.items():
                wk_fb.setdefault(w, []).extend(m)
        if not sk_fb and not wk_fb:
            done -= 1
            break
        log(f"[repair {done}] skeleton {len(sk_fb)} · weeks {sorted(wk_fb)}")
        new_sk = run_skeleton(sk_fb) if sk_fb else []
        new_wk = run_weeks(sorted(wk_fb), wk_fb) if wk_fb else {}
        sk_fb, wk_fb = new_sk, new_wk

    sk_l, wk_l, warns = lint_issues(pk)
    sk_q, wk_q = quality_issues(pk, first=False)
    sk_l += sk_q
    for w, m in wk_q.items():
        wk_l.setdefault(w, []).extend(f"weeks[{w}] {x}" for x in m)
    for w, m in wk_fb.items():                    # 마지막 재작성의 조립 문제(출처 대체 등)도 남긴다
        wk_l.setdefault(w, []).extend(f"weeks[{w}] {x}" for x in m)
    errors = sk_fb + sk_l + [m for _, ms in sorted(wk_l.items()) for m in ms]
    return {"pack": pk, "errors": errors, "warnings": warns, "rounds": done, "calls": calls}


def review_md(b: Dict, res: Dict) -> str:
    pk = res["pack"]
    lines = [f"# 초안 검수 메모 — {pk['name']} (`{pk['id']}`)", "",
             f"- 생성: scripts/pack_draft.py · LLM 호출 {res['calls']}회 · 수리 {res['rounds']}회",
             f"- lint error {len(res['errors'])} · warning {len(res['warnings'])}",
             "- **이 파일은 초안이다.** 사람이 읽고 고친 뒤 `routines/packs/<id>/v1.json` 으로 옮기고 "
             "`python scripts/pack_lint.py <id>` 를 통과시켜 PR 을 올린다.", "",
             "## 사람이 꼭 볼 것", "",
             "- [ ] 출처가 각 행동을 실제로 뒷받침하는가(LLM 은 key 만 골랐다)",
             "- [ ] 1주차·정착기 마지막 주·복구 주차·마지막 주 행동을 소리 내 읽어 봤다",
             "- [ ] 난이도가 대상에게 맞고 주차마다 조금씩 나아가는가",
             "- [ ] 문진 value 와 보조 행동 규칙이 말이 되는가"]
    if pk["safety_profile"] == "physical":
        lines.append("- [ ] warning_actions 가 운동을 쉬게 하는 쪽인가, 통증 처방이 없는가")
    if res["errors"]:
        lines += ["", "## 남은 lint error", ""] + [f"- {e}" for e in res["errors"]]
    if res["warnings"]:
        lines += ["", "## 경고", ""] + [f"- {w}" for w in res["warnings"]]
    lines += ["", "## 주차 한눈에", "", "| 주 | 단계 | 테마 | " + " | ".join(t["name"] for t in pk["tracks"]) + " |",
              "|---|---|---|" + "---|" * len(pk["tracks"])]
    ph = {w: p["name"] for p in pk["phases"] for w in range(p["from"], p["to"] + 1)}
    for w in pk["weeks"]:
        acts = " | ".join(f"{w['actions'][t['id']]['text']} ({w['actions'][t['id']]['input']['kind']})"
                          for t in pk["tracks"])
        lines.append(f"| {w['w']} | {ph[w['w']]} | {w['theme']} | {acts} |")
    return "\n".join(lines) + "\n"


def write_draft(res: Dict, brief: Dict, out_dir: Optional[pathlib.Path] = None) -> pathlib.Path:
    d = pathlib.Path(out_dir or DRAFTS_DIR) / res["pack"]["id"]
    if d.resolve().is_relative_to(rp.PACKS_DIR.resolve()):
        raise ValueError("초안은 routines/packs 에 쓰지 않는다")
    d.mkdir(parents=True, exist_ok=True)
    f = d / "v1.json"
    f.write_text(json.dumps(res["pack"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (d / "review.md").write_text(review_md(brief, res), encoding="utf-8")
    return f


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("brief")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--effort", default="low", choices=["minimal", "low", "medium", "high"])
    ap.add_argument("--out", default="", help="기본: routines/drafts")
    a = ap.parse_args(argv)
    try:
        b = load_brief(a.brief)
    except BriefError as e:
        print(f"brief: {e}", file=sys.stderr)
        return 2
    res = draft(b, default_llm(a.effort), rounds=a.rounds)
    f = write_draft(res, b, pathlib.Path(a.out) if a.out else None)
    print(f"wrote {f} — error {len(res['errors'])} · warning {len(res['warnings'])} · 호출 {res['calls']}회")
    print(f"검수 메모: {f.parent / 'review.md'}")
    return 0 if not res["errors"] else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
