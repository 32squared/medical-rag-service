"""pack_lint.py — 루틴 팩 검사기(28 §4-6 L1~L11). CI 게이트.

    python scripts/pack_lint.py --all              # 전 팩·전 버전
    python scripts/pack_lint.py golf_6m            # 한 팩(모든 버전)
    python scripts/pack_lint.py path/to/v1.json    # 파일 하나(초안 검사)
    python scripts/pack_lint.py --all --warn       # 경고까지 출력
    python scripts/pack_lint.py --schema           # routines/_schema/pack.schema.json 갱신

출력: `파일:경로:규칙:메시지`. error 가 있으면 exit 1.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import routine_packs as rp  # noqa: E402

SCHEMA_FILE = ROOT / "routines" / "_schema" / "pack.schema.json"


def schema_text() -> str:
    return json.dumps(rp.json_schema(), ensure_ascii=False, indent=1) + "\n"


def _files(args):
    if "--all" in args or not [a for a in args if not a.startswith("--")]:
        return sorted(rp.PACKS_DIR.glob("*/v*.json"))
    out = []
    for a in args:
        if a.startswith("--"):
            continue
        p = pathlib.Path(a)
        out += [p] if p.suffix == ".json" else sorted((rp.PACKS_DIR / a).glob("v*.json"))
    return out


def lint_file(path: pathlib.Path, show_warn: bool = False):
    """(error 수, 출력 줄) — 구조 오류는 L1 로 보고하고 내용 lint 는 건너뛴다."""
    name = path.as_posix()
    try:
        pack = rp.load_file(path) if path.parent.parent == rp.PACKS_DIR else \
            rp.Pack.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as e:                          # noqa: BLE001
        return 1, [f"{name}:-:L1:{e}"]
    lines, errs = [], 0
    for i in rp.lint(pack):
        if i["level"] == "error":
            errs += 1
        elif not show_warn:
            continue
        lines.append(f"{name}:{i['path']}:{i['rule']}{'' if i['level'] == 'error' else '(warn)'}:{i['msg']}")
    return errs, lines


def main(argv) -> int:
    if "--schema" in argv:
        SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_FILE.write_text(schema_text(), encoding="utf-8")
        print(f"wrote {SCHEMA_FILE.relative_to(ROOT)}")
        return 0
    total = 0
    files = _files(argv)
    for f in files:
        n, lines = lint_file(f, "--warn" in argv)
        total += n
        for ln in lines:
            print(ln)
    print(f"{len(files)} file(s), {total} error(s)")
    return 1 if total else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
