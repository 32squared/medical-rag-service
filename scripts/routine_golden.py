"""routine_golden.py — 건강 12주 커리큘럼의 골든 스냅샷(팩 플랫폼 무회귀 기준).

정본: docs/plan/28-routine-pack-platform.md FR-S3.

`build()` 는 엔진·문진·보조 풀·프로그램 생성의 공개 출력을 결정적으로 모은다.
tests/golden/health_12w.json 은 팩 플랫폼 도입 **전** 코드로 만든 기준본이고,
tests/test_routine_packs.py 가 이후 코드의 `build()` 결과와 동등 비교한다.

재생성은 의도적으로 동작을 바꿀 때만:
    python scripts/routine_golden.py --write
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "tests" / "golden" / "health_12w.json"
BANDS = [None, "안정", "주의", "경고"]
TRACKS = ["diet", "exercise", "habit"]


def _intake_combos(questions):
    """문항별 선택지 전 조합 + 빈 문진."""
    ids = [q["id"] for q in questions]
    opts = [q["options"] for q in questions]
    out = [{}]
    for combo in itertools.product(*opts):
        out.append(dict(zip(ids, combo)))
    return out


def build() -> dict:
    import coaching_engine as ce
    import routine_engine as eng

    engine = {}
    for w in range(1, 13):
        engine[str(w)] = {
            "phase": eng.phase_of(w),
            "meta": eng.week_meta(w),
            "goal_days": eng.goal_days(w),
            "ask_chips": eng.ask_chips(w),
            "actions": {t: eng.today_action(w, t) for t in TRACKS},
            "band_cap": {str(b): eng.band_cap(b, w) for b in BANDS},
        }

    banners = {t: {str(b): eng.banner_for(t, b) for b in BANDS} for t in TRACKS}
    preview = {str(b): eng.week_preview(b) for b in BANDS}
    transition = {f"{d}/{g}/{b}": eng.transition(d, g, b)
                  for d in range(0, 8) for g in range(1, 8) for b in BANDS}

    intake = {t: ce.get_intake(t) for t in TRACKS}
    plans, programs, support = {}, {}, {}
    for t in TRACKS:
        for i, combo in enumerate(_intake_combos(intake[t])):
            for b in BANDS:
                key = f"{t}|{i}|{b}"
                plan = ce.generate_plan(t, combo, band=b)
                plans[key] = {"intake": combo, **plan}
                prog = eng.generate_program(t, combo, band=b, focus=None, anchor=None)
                prog = {k: v for k, v in prog.items() if k != "weeks"}   # weeks = preview 와 동일
                programs[key] = prog
                skey = f"{t}|{','.join(x['key'] for x in plan['items'])}|{b}"   # 풀이 같으면 결과도 같다
                if skey not in support:
                    support[skey] = {str(w): eng.support_items(plan["items"], w, b) for w in range(1, 13)}

    return {
        "engine": engine,
        "banners": banners,
        "week_preview": preview,
        "transition": transition,
        "intake": intake,
        "coaching_plans": plans,
        "programs": programs,
        "support_items": support,
        "tracks": list(eng.TRACKS),
        "weeks_total": eng.WEEKS_TOTAL,
        "curriculum_version": eng.CURRICULUM_VERSION,
    }


def dump(obj) -> str:
    """최상위 키 한 줄씩 — diff 가 어느 블록에서 났는지 보이게, 크기는 작게."""
    rows = [f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(obj[k], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
            for k in sorted(obj)]
    return "{\n" + ",\n".join(rows) + "\n}"


if __name__ == "__main__":
    data = build()
    if "--write" in sys.argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(dump(data) + "\n", encoding="utf-8")
        print(f"wrote {GOLDEN.relative_to(ROOT)} ({GOLDEN.stat().st_size:,} bytes)")
    else:
        cur = json.loads(GOLDEN.read_text(encoding="utf-8"))
        print("MATCH" if cur == json.loads(dump(data)) else "DIFF")
