"""pack_new.py — 빈 루틴 팩 스캐폴드(28 FR-T2).

    python scripts/pack_new.py --id golf_6m --weeks 26 --tracks range,home \
        --profile physical --domain sport --name "골프 6개월 루틴"

구조(L1·L2)는 처음부터 유효하고, 문구 자리는 전부 `TODO` 라서 lint L0 가 실패한다.
TODO 를 다 채우고 `python scripts/pack_lint.py <id>` 가 0 error 가 되면 PR 을 올린다.
단계는 4개(정착 → 쌓기 → 써먹기 → 유지)로 기간에 비례해 나눈다. 필요하면 고친다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import routine_packs as rp  # noqa: E402


def phases_for(n: int):
    """정착 약 12% · 쌓기 약 40% · 써먹기 약 30% · 유지 나머지(최소 1주씩)."""
    if n < 4:
        raise ValueError("weeks 는 4 이상(단계 4개 × 최소 1주)")
    size = {"settle": max(1, round(n * 0.12)), "build": max(1, round(n * 0.40)),
            "use": max(1, round(n * 0.30))}
    while sum(size.values()) > n - 1:                 # 유지 1주를 남길 때까지 큰 단계부터 줄인다
        size[max(size, key=size.get)] -= 1
    settle, build, use = size["settle"], size["build"], size["use"]
    keep = n - settle - build - use
    spans, start = [], 1
    for pid, name, size in (("settle", "정착기", settle), ("build", "쌓기", build),
                            ("use", "써먹기", use), ("keep", "유지", keep)):
        spans.append({"id": pid, "name": name, "from": start, "to": start + size - 1, "desc": "TODO"})
        start += size
    return spans


def scaffold(pid, weeks, tracks, profile, domain, name):
    phases = phases_for(weeks)
    settle_to = phases[0]["to"]
    wk = []
    for w in range(1, weeks + 1):
        wk.append({
            "w": w, "theme": "TODO", "goal_days": 3 if w == 1 else 5,
            "support_cap": 0 if w <= settle_to else 1, "mission": "TODO", "unlock": None,
            "actions": {t: {"id": f"w{w}:{t}", "text": "TODO", "cite": "TODO_SOURCE",
                            "minutes": 10, "input": {"kind": "tap", "options": []}} for t in tracks},
            "ask_chips": ["TODO", "TODO", "TODO"],
        })
        if profile in ("medical", "physical"):          # 경고 밴드 치환 행동(L9)
            wk[-1]["warning_actions"] = {
                t: {"id": f"w{w}:{t}:warn", "text": "TODO", "cite": "TODO_SOURCE", "minutes": 5,
                    "input": {"kind": "tap", "options": []}} for t in tracks}
    pack = {
        "schema_version": rp.SCHEMA_VERSION, "id": pid, "version": 1, "name": name or "TODO",
        "tagline": "TODO", "domain": domain, "safety_profile": profile, "weeks_total": weeks,
        "phases": phases,
        "tracks": [{"id": t, "name": "TODO", "icon": "star", "desc": "TODO", "target_noun": ""}
                   for t in tracks],
        "intake": {t: [] for t in tracks},
        "weeks": wk,
        "support_pool": {t: [] for t in tracks},
        "support_rules": {t: {"rules": [], "default": []} for t in tracks},
        "banners": ({t: {"주의": "TODO", "경고": "TODO"} for t in tracks}
                    if profile in ("medical", "physical") else {}),
        "transition": {"advance": 0.7, "simplify": 0.4},
        "sources": [{"key": "TODO_SOURCE", "label": "TODO", "url": None}],
    }
    rp.Pack.model_validate(pack)                     # 구조는 유효해야 한다
    return pack


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--weeks", type=int, required=True)
    ap.add_argument("--tracks", required=True, help="콤마 구분 트랙 id")
    ap.add_argument("--profile", choices=sorted(rp.SAFETY_PROFILES), required=True)
    ap.add_argument("--domain", default="custom")
    ap.add_argument("--name", default="")
    ap.add_argument("--out", default="", help="기본: routines/packs/<id>/v1.json")
    a = ap.parse_args(argv)
    pack = scaffold(a.id, a.weeks, [t.strip() for t in a.tracks.split(",") if t.strip()],
                    a.profile, a.domain, a.name)
    out = pathlib.Path(a.out) if a.out else rp.PACKS_DIR / a.id / "v1.json"
    if out.exists():
        print(f"exists: {out}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out} — TODO 를 채우고 scripts/pack_lint.py {a.id} 로 검사하세요")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
