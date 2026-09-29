"""routine_packs.py — 루틴 팩 모델·로더·레지스트리.

정본: docs/plan/28-routine-pack-platform.md §3·§4.

루틴 하나 = 팩 파일 하나(`routines/packs/<id>/v<version>.json`). 엔진·저장소·API·화면은
팩을 읽어서 동작한다. 이 모듈은 두 가지를 보장한다.

  1. **구조 무결성**(L1·L2): 주차 수·단계 경계·트랙 참조·출처 참조·보조 규칙 참조가
     어긋난 팩은 로드 자체가 실패한다. 잘못된 팩이 조용히 서빙되지 않는다.
  2. **버전 고정**: 프로그램은 시작 시점의 (pack_id, version) 을 기억하고, 팩을 고쳐
     배포해도 그 버전으로 계속 간다. 버전 파일은 지우지 않는다.

내용 규칙(글자수·금칙·정착기 원칙 등 L3~L11)은 `lint()` 가 검사한다(CI 게이트).
안전 불변식(응급 중단·밴드 캡·WC-C 스캔)은 팩이 아니라 `SAFETY_PROFILES` 가 정한다.
"""
from __future__ import annotations

import json
import pathlib
import re
import threading
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PACKS_DIR = pathlib.Path(__file__).resolve().parent / "routines" / "packs"
DEFAULT_PACK_ID = "health_12w"
SCHEMA_VERSION = 1

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_FILE_RE = re.compile(r"^v(\d+)\.json$")
BANDS_CAPPED = ("주의", "경고")


# ══════════════════════════ 안전 프로필(플랫폼 불변식) ══════════════════════════
# 팩은 프로필을 고를 수만 있고 규칙을 끌 수 없다(28 §3-2).
#   band_max: 밴드별 보조 행동 상한(주차 support_cap 과 min). None 키 = 밴드 없음/안정.
#   advance_block: 이 밴드에서 주차 advance 금지.
#   banner_required: 이 밴드들의 트랙별 배너가 팩에 있어야 함(lint L9).
SAFETY_PROFILES: Dict[str, Dict] = {
    "medical": {"band_max": {"안정": 2, "주의": 1, "경고": 0}, "default_max": 2,
                "advance_block": ("경고",), "banner_required": ("주의", "경고")},
    "physical": {"band_max": {"안정": 2, "주의": 1, "경고": 0}, "default_max": 2,
                 "advance_block": ("경고",), "banner_required": ("주의", "경고")},
    "neutral": {"band_max": {}, "default_max": 2,
                "advance_block": (), "banner_required": ()},
}


# ══════════════════════════ 모델 ══════════════════════════
class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Source(_M):
    key: str
    label: str
    url: Optional[str] = None


class Phase(_M):
    id: str
    name: str
    from_: int = Field(alias="from", ge=1)
    to: int = Field(ge=1)
    desc: str = ""


class Track(_M):
    id: str
    name: str
    icon: str = "star"
    desc: str = ""
    target_noun: str = ""
    recommend_when: List[str] = []     # medical 팩만: /diagnosis focus 신호


class Option(_M):
    label: str
    value: str


class IntakeQ(_M):
    id: str
    q: str
    options: List[Option]
    why: Optional[str] = None


class Input(_M):
    kind: Literal["tap", "choice", "scale"]
    options: List[str] = []


class Action(_M):
    id: str
    text: str
    cite: str                           # sources[].key
    minutes: int = Field(ge=1, le=60)
    input: Input


class Week(_M):
    w: int = Field(ge=1)
    theme: str
    goal_days: int = Field(ge=1, le=7)
    support_cap: int = Field(ge=0, le=2)
    mission: str
    unlock: Optional[str] = None
    actions: Dict[str, Action]
    ask_chips: List[str] = []
    warning_actions: Dict[str, Action] = {}   # 경고 밴드 치환(27 §2-5), 없으면 원행동


class SupportItem(_M):
    key: str
    text: str
    cite: str
    tags: List[str] = []


class SupportRule(_M):
    """누적 규칙: 조건이 맞으면 `add` 를 순서대로 붙인다(첫 매치가 아님).

    when   : {문항 id: [허용 value...]}  — 모두 만족해야(AND). 값 목록의 null = 미응답.
    unless : {문항 id: [value...]}       — 하나라도 해당하면 제외.
    조건이 둘 다 없으면 항상 적용.
    """
    when: Dict[str, List[Optional[str]]] = {}
    unless: Dict[str, List[Optional[str]]] = {}
    add: List[str]


class TrackSupport(_M):
    rules: List[SupportRule] = []
    default: List[str] = []            # 규칙 결과가 비었을 때


class Transition(_M):
    advance: float = Field(0.7, gt=0, le=1)
    simplify: float = Field(0.4, ge=0, lt=1)


class Pack(_M):
    schema_version: Literal[1] = 1
    id: str
    version: int = Field(ge=1)
    name: str
    tagline: str = ""
    domain: Literal["health", "sport", "language", "hobby", "study", "custom"]
    safety_profile: Literal["medical", "physical", "neutral"]
    weeks_total: int = Field(ge=4, le=52)
    phases: List[Phase]
    tracks: List[Track]
    intake: Dict[str, List[IntakeQ]] = {}
    weeks: List[Week]
    support_pool: Dict[str, List[SupportItem]] = {}
    support_rules: Dict[str, TrackSupport] = {}
    support_pool_cap: Dict[str, int] = {"default": 4}   # 밴드별 풀 크기 상한(예: 경고 2)
    banners: Dict[str, Dict[str, str]] = {}
    transition: Transition = Transition()
    sources: List[Source]

    # ── 구조 무결성(L1·L2) ──────────────────────────────────────
    @field_validator("id")
    @classmethod
    def _id_ok(cls, v):
        if not _ID_RE.match(v):
            raise ValueError(f"pack id '{v}' must match {_ID_RE.pattern}")
        return v

    @model_validator(mode="after")
    def _integrity(self):
        errs: List[str] = []
        n = self.weeks_total
        track_ids = [t.id for t in self.tracks]
        tset = set(track_ids)
        src = {s.key for s in self.sources}

        if not self.tracks:
            errs.append("tracks: at least one track")
        if len(tset) != len(track_ids):
            errs.append("tracks: duplicate id")
        for t in track_ids:
            if not _ID_RE.match(t):
                errs.append(f"tracks.{t}: id must match {_ID_RE.pattern}")
        if len(src) != len(self.sources):
            errs.append("sources: duplicate key")

        # L1 주차·단계
        if [w.w for w in self.weeks] != list(range(1, n + 1)):
            errs.append(f"weeks: must be w=1..{n} in order (got {len(self.weeks)})")
        cover = []
        for p in sorted(self.phases, key=lambda p: p.from_):
            if p.to < p.from_:
                errs.append(f"phases.{p.id}: to < from")
            cover.extend(range(p.from_, p.to + 1))
        if cover != list(range(1, n + 1)):
            errs.append(f"phases: must cover 1..{n} without gaps or overlap")
        if len({p.id for p in self.phases}) != len(self.phases):
            errs.append("phases: duplicate id")

        # L2 참조 무결성
        for w in self.weeks:
            if set(w.actions) != tset:
                errs.append(f"weeks[{w.w}].actions: keys {sorted(w.actions)} != tracks {sorted(tset)}")
            if not set(w.warning_actions) <= tset:
                errs.append(f"weeks[{w.w}].warning_actions: unknown track")
            for t, a in list(w.actions.items()) + list(w.warning_actions.items()):
                if a.cite not in src:
                    errs.append(f"weeks[{w.w}].actions.{t}.cite '{a.cite}' not in sources")
                if a.input.kind in ("choice", "scale") and len(a.input.options) < 2:
                    errs.append(f"weeks[{w.w}].actions.{t}.input: {a.input.kind} needs >=2 options")
        for t in track_ids:                     # 행동 id 는 트랙 안에서 주차 간 유일
            ids = [w.actions[t].id for w in self.weeks if t in w.actions]
            if len(ids) != len(set(ids)):
                errs.append(f"weeks.*.actions.{t}: duplicate action id")

        for section in ("intake", "support_pool", "support_rules", "banners"):
            extra = set(getattr(self, section)) - tset
            if extra:
                errs.append(f"{section}: unknown tracks {sorted(extra)}")
        for t, qs in self.intake.items():
            if len({q.id for q in qs}) != len(qs):
                errs.append(f"intake.{t}: duplicate question id")
        for t, pool in self.support_pool.items():
            keys = [x.key for x in pool]
            if len(keys) != len(set(keys)):
                errs.append(f"support_pool.{t}: duplicate key")
            for x in pool:
                if x.cite not in src:
                    errs.append(f"support_pool.{t}.{x.key}.cite '{x.cite}' not in sources")
        for t, sr in self.support_rules.items():
            keys = {x.key for x in self.support_pool.get(t, [])}
            qids = {q.id for q in self.intake.get(t, [])}
            for i, r in enumerate(sr.rules):
                for k in r.add:
                    if k not in keys:
                        errs.append(f"support_rules.{t}.rules[{i}]: '{k}' not in support_pool")
                for q in list(r.when) + list(r.unless):
                    if q not in qids:
                        errs.append(f"support_rules.{t}.rules[{i}]: unknown intake id '{q}'")
            for k in sr.default:
                if k not in keys:
                    errs.append(f"support_rules.{t}.default: '{k}' not in support_pool")
        for t, b in self.banners.items():
            bad = set(b) - set(BANDS_CAPPED)
            if bad:
                errs.append(f"banners.{t}: unknown bands {sorted(bad)}")
        if "default" not in self.support_pool_cap:
            errs.append("support_pool_cap: needs 'default'")

        if errs:
            raise ValueError("pack integrity:\n  - " + "\n  - ".join(errs))
        return self

    # ── 편의 조회 ────────────────────────────────────────────────
    @property
    def track_ids(self) -> List[str]:
        return [t.id for t in self.tracks]

    @property
    def default_track(self) -> str:
        return self.tracks[0].id

    @property
    def profile(self) -> Dict:
        return SAFETY_PROFILES[self.safety_profile]

    def source_label(self, key: str) -> str:
        for s in self.sources:
            if s.key == key:
                return s.label
        return key

    def track(self, track_id: Optional[str]) -> Track:
        for t in self.tracks:
            if t.id == track_id:
                return t
        return self.tracks[0]


# ══════════════════════════ 레지스트리 ══════════════════════════
_LOCK = threading.Lock()
_REGISTRY: Optional[Dict[Tuple[str, int], Pack]] = None


def load_file(path: pathlib.Path) -> Pack:
    data = json.loads(path.read_text(encoding="utf-8"))
    pack = Pack.model_validate(data)
    m = _FILE_RE.match(path.name)
    if not m or int(m.group(1)) != pack.version or path.parent.name != pack.id:
        raise ValueError(f"{path}: file must be routines/packs/{pack.id}/v{pack.version}.json")
    return pack


def load_all(packs_dir: Optional[pathlib.Path] = None) -> Dict[Tuple[str, int], Pack]:
    """전 팩·전 버전 로드. 하나라도 틀리면 RuntimeError — 서버 기동을 막는다."""
    packs_dir = pathlib.Path(packs_dir or PACKS_DIR)
    reg: Dict[Tuple[str, int], Pack] = {}
    errors: List[str] = []
    for path in sorted(packs_dir.glob("*/v*.json")):
        try:
            p = load_file(path)
            reg[(p.id, p.version)] = p
        except Exception as e:                     # noqa: BLE001 — 모아서 한 번에 보고
            errors.append(f"{path.parent.name}/{path.name}: {e}")
    if errors:
        raise RuntimeError("invalid routine pack(s):\n" + "\n".join(errors))
    if not any(pid == DEFAULT_PACK_ID for pid, _ in reg):
        raise RuntimeError(f"default pack '{DEFAULT_PACK_ID}' missing in {packs_dir}")
    return reg


def registry() -> Dict[Tuple[str, int], Pack]:
    global _REGISTRY
    if _REGISTRY is None:
        with _LOCK:
            if _REGISTRY is None:
                _REGISTRY = load_all()
    return _REGISTRY


def reload() -> None:
    """테스트·개발용."""
    global _REGISTRY
    with _LOCK:
        _REGISTRY = load_all()


def pack_ids() -> List[str]:
    return sorted({pid for pid, _ in registry()})


def latest_version(pack_id: str) -> Optional[int]:
    vs = [v for pid, v in registry() if pid == pack_id]
    return max(vs) if vs else None


def exists(pack_id: Optional[str]) -> bool:
    return bool(pack_id) and latest_version(pack_id) is not None


def get(pack_id: Optional[str] = None, version: Optional[int] = None) -> Pack:
    """(id, version) 팩. id 없거나 모르면 기본 팩, version 없거나 모르면 최신.

    진행 중 프로그램이 참조하는 팩이 사라져도 화면이 깨지지 않게 폴백한다.
    """
    reg = registry()
    pid = pack_id if exists(pack_id) else DEFAULT_PACK_ID
    try:
        v = int(version) if version is not None else None
    except (TypeError, ValueError):
        v = None
    if v is not None and (pid, v) in reg:
        return reg[(pid, v)]
    return reg[(pid, latest_version(pid))]


def catalog() -> List[Pack]:
    """최신 버전만, 기본 팩 먼저."""
    out = [get(pid) for pid in pack_ids()]
    out.sort(key=lambda p: (p.id != DEFAULT_PACK_ID, p.id))
    return out


def json_schema() -> Dict:
    return Pack.model_json_schema(by_alias=True)


# ══════════════════════════ 내용 lint(L3~L11, 28 §4-6) ══════════════════════════
# 구조(L1·L2)는 모델 검증이 막는다. 여기는 "타당한 루틴" 의 기계 검사 — CI 게이트.
# 결과: [{"rule", "level": "error"|"warn", "path", "msg"}]. error 가 하나라도 있으면 배포 불가.

# 화면 레이아웃 예산(27 §0-4 + 28 §4). 폰트 200%·2줄 기준에서 버튼이 밀리지 않는 길이.
BUDGET = {
    "name": 20, "tagline": 30, "track.name": 12, "track.desc": 40, "phase.name": 8,
    "phase.desc": 30, "theme": 20, "mission": 40, "unlock": 20, "action": 30,
    "option": 12, "chip": 24, "intake.q": 24, "intake.why": 20, "intake.option": 16,
    "support": 30, "banner": 80,
}
# 아이콘 키(web/js/archetypes.js ICON 과 동기 — 테스트가 확인). 이모지 금지(design.md).
ICONS = {"star", "flame", "cup", "cloud", "bowl", "run", "moon", "book", "headphones",
         "golf", "home", "pen", "leaf", "music"}
# 무비난 원칙(27 §0-1·§0-2 금칙 4) — 미실천을 규정하는 말
_BLAME = re.compile(r"(실패|미달|놓친|놓쳤|결석|또\s*못|게으|벌칙|낙오|포기했)")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
_TODO = re.compile(r"\bTODO\b")
TAP_SHARE_MAX = 0.6                     # 트랙별 tap 행동 비율 상한(권고). 기존 팩 25~50%
_ANCHOR = re.compile(r"(anchor|when|time|언제|시각|시간대)")
# medical 프로필 출처 화이트리스트(공신력 보건 기관)
_MEDICAL_SOURCES = re.compile(r"(질병관리청|질병청|식품의약품안전처|식약처|국민건강보험공단|건강보험|"
                              r"WHO|보건소|국민체육진흥|한국건강증진개발원|보건복지부)")
# 이전 코드에서 넘어온 팩의 예외(28 §10 리스크 1). 해당 규칙은 경고로만 낸다.
LEGACY_WARN_ONLY: Dict[str, Tuple[str, ...]] = {
    "health_12w": ("L3", "L10"),     # 27 §2 교체본 카피 반영은 별도 PR
}


def _texts(p: Pack):
    """(경로, 텍스트, 예산 키) 전수."""
    yield "name", p.name, "name"
    yield "tagline", p.tagline, "tagline"
    for t in p.tracks:
        yield f"tracks.{t.id}.name", t.name, "track.name"
        yield f"tracks.{t.id}.desc", t.desc, "track.desc"
    for ph in p.phases:
        yield f"phases.{ph.id}.name", ph.name, "phase.name"
        yield f"phases.{ph.id}.desc", ph.desc, "phase.desc"
    for t, qs in p.intake.items():
        for q in qs:
            yield f"intake.{t}.{q.id}.q", q.q, "intake.q"
            if q.why:
                yield f"intake.{t}.{q.id}.why", q.why, "intake.why"
            for o in q.options:
                yield f"intake.{t}.{q.id}.option", o.label, "intake.option"
    for w in p.weeks:
        yield f"weeks[{w.w}].theme", w.theme, "theme"
        yield f"weeks[{w.w}].mission", w.mission, "mission"
        if w.unlock:
            yield f"weeks[{w.w}].unlock", w.unlock, "unlock"
        for i, c in enumerate(w.ask_chips):
            yield f"weeks[{w.w}].ask_chips[{i}]", c, "chip"
        for kind, acts in (("actions", w.actions), ("warning_actions", w.warning_actions)):
            for t, a in acts.items():
                yield f"weeks[{w.w}].{kind}.{t}.text", a.text, "action"
                for o in a.input.options:
                    yield f"weeks[{w.w}].{kind}.{t}.option", o, "option"
    for t, pool in p.support_pool.items():
        for x in pool:
            yield f"support_pool.{t}.{x.key}", x.text, "support"
    for t, b in p.banners.items():
        for band, txt in b.items():
            yield f"banners.{t}.{band}", txt, "banner"


def lint(p: Pack) -> List[Dict]:
    import coaching_compliance as cc

    out: List[Dict] = []
    soft = set(LEGACY_WARN_ONLY.get(p.id, ()))

    def add(rule, path, msg, level="error"):
        if level == "error" and rule in soft:
            level = "warn"
        out.append({"rule": rule, "level": level, "path": path, "msg": msg})

    for path, txt, key in _texts(p):
        if not txt:
            continue
        if _TODO.search(txt):
            add("L0", path, "TODO 자리표시자가 남아 있음")
        if len(txt) > BUDGET[key]:
            add("L3", path, f"{len(txt)}자 > 예산 {BUDGET[key]}자({key})")
        chk = cc.check_plan(txt, None, profile=p.safety_profile)
        if not chk["ok"]:
            add("L4", path, f"컴플라 {chk['action']}: {chk['violations']}")
        m = _BLAME.search(txt)
        if m:
            add("L5", path, f"무비난 금칙어 '{m.group(0)}'")
        if _EMOJI.search(txt):
            add("L10", path, "이모지 금지 — 아이콘 키를 쓴다")

    # L6 출처
    if p.safety_profile == "medical":
        for s in p.sources:
            if not _MEDICAL_SOURCES.search(s.label):
                add("L6", f"sources.{s.key}", f"medical 팩 출처는 공신력 보건 기관만: '{s.label}'")
    used = {a.cite for w in p.weeks for a in list(w.actions.values()) + list(w.warning_actions.values())}
    used |= {x.cite for pool in p.support_pool.values() for x in pool}
    for s in p.sources:
        if s.key not in used:
            add("L6", f"sources.{s.key}", "쓰이지 않는 출처", "warn")

    # L7 입력 위젯
    for w in p.weeks:
        for kind, acts in (("actions", w.actions), ("warning_actions", w.warning_actions)):
            for t, a in acts.items():
                n = len(a.input.options)
                path = f"weeks[{w.w}].{kind}.{t}.input"
                if a.input.kind == "choice" and not 2 <= n <= 5:
                    add("L7", path, f"choice 옵션은 2~5개(현재 {n})")
                if a.input.kind == "scale" and not 3 <= n <= 5:
                    add("L7", path, f"scale 라벨은 3~5개(현재 {n})")
                if a.input.kind == "tap" and n:
                    add("L7", path, "tap 은 옵션을 두지 않는다")

    # L8 커리큘럼 원칙
    first = p.phases[0] if p.phases else None
    if p.weeks and p.weeks[0].goal_days > 3:
        add("L8", "weeks[1].goal_days", "첫 주 목표는 3일 이하 권고(첫 성공 경험)", "warn")
    if first and p.safety_profile in ("medical", "physical"):
        for w in p.weeks:
            if first.from_ <= w.w <= first.to and w.support_cap:
                add("L8", f"weeks[{w.w}].support_cap", "정착기에는 보조 행동을 얹지 않는다(0)")
    for t in p.track_ids:                             # P1 하고 "남기기" — 느낌·양·상황을 고르는 주차
        taps = sum(w.actions[t].input.kind == "tap" for w in p.weeks)
        if p.weeks and taps / len(p.weeks) > TAP_SHARE_MAX:
            add("L8", f"weeks.*.actions.{t}.input",
                f"P1 tap 비율 {taps}/{len(p.weeks)} — choice·scale 로 남길 거리를 권고", "warn")
    if len(p.phases) < 4:
        add("L8", "phases", "P3 단계 4개 권고(정착→확장→내재화→유지)", "warn")
    for t, qs in p.intake.items():                   # P4 앵커링 — "언제 할지" 문항
        if not any(_ANCHOR.search(q.id) or _ANCHOR.search(q.q) for q in qs):
            add("L8", f"intake.{t}", "P4 앵커(언제 할지) 문항 권고", "warn")
    later = [w for w in p.weeks if len(p.phases) >= 3 and w.w >= p.phases[2].from_]
    for t in p.track_ids:                             # P5 복구 — 내재화기 이후 tap 행동
        if later and not any(w.actions[t].input.kind == "tap" for w in later):
            add("L8", f"weeks.*.actions.{t}", "P5 내재화기 이후 복구용 tap 행동 권고", "warn")

    # L9 밴드 배너
    for band in p.profile["banner_required"]:
        for t in p.track_ids:
            if not p.banners.get(t, {}).get(band):
                add("L9", f"banners.{t}.{band}", f"{p.safety_profile} 팩은 {band} 배너 필수")
    # 경고 밴드 치환 행동 — physical 은 필수(운동을 그대로 시키지 않는다), medical 은 권고
    if p.safety_profile in ("medical", "physical"):
        lvl = "error" if p.safety_profile == "physical" else "warn"
        for w in p.weeks:
            miss = [t for t in p.track_ids if t not in w.warning_actions]
            if miss:
                add("L9", f"weeks[{w.w}].warning_actions", f"경고 밴드 치환 행동 없음: {miss}", lvl)

    # L10 아이콘
    for t in p.tracks:
        if t.icon not in ICONS:
            add("L10", f"tracks.{t.id}.icon", f"알 수 없는 아이콘 '{t.icon}'(허용: {sorted(ICONS)})")

    # L11 질문칩
    for w in p.weeks:
        if len(w.ask_chips) != 3:
            add("L11", f"weeks[{w.w}].ask_chips", f"질문칩은 3개(현재 {len(w.ask_chips)})")
    return out


def lint_errors(p: Pack) -> List[Dict]:
    return [x for x in lint(p) if x["level"] == "error"]
