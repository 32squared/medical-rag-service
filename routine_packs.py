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
