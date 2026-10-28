"""
collect_kb.py — 카탈로그 기반 KB 자동 구축 CLI (Cloud Run 잡 진입점).

  python collect_kb.py --status                 # 출처별 상태·사람이 해 줄 일
  python collect_kb.py --source mfds_dur --dry-run
  python collect_kb.py --due                    # cadence 가 지난 active 출처만
  python collect_kb.py --all                    # active 출처 전부
  python collect_kb.py --runs                   # 최근 실행 기록
"""
from __future__ import annotations

import argparse
import json
import sys


def _print_status():
    import kb_catalog
    rows = kb_catalog.status_table()
    w = max(len(r["id"]) for r in rows) + 1
    print(f"{'id'.ljust(w)} {'effective':16} {'license':16} {'access':16} needs")
    for r in rows:
        print(f"{r['id'].ljust(w)} {str(r['effective']):16} {str(r['license']):16} {r['access']:16} {r['needs']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="카탈로그 기반 KB 자동 구축")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--runs", action="store_true")
    ap.add_argument("--source", help="쉼표로 구분한 출처 id")
    ap.add_argument("--all", action="store_true", help="active 출처 전부")
    ap.add_argument("--due", action="store_true", help="갱신 주기가 지난 출처만")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=200)
    args = ap.parse_args(argv)

    if args.status:
        _print_status()
        return 0
    if args.runs:
        from kb_collect import ledger
        for r in ledger.recent_runs(30):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if not (args.source or args.all or args.due):
        ap.print_help()
        return 2
    from kb_collect.runner import run_sources
    ids = [s.strip() for s in args.source.split(",")] if args.source else None
    res = run_sources(ids, dry_run=args.dry_run, max_items=args.max, only_due=args.due)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    bad = [r for r in res["runs"] if r["status"] not in ("ok",)]
    return 1 if bad or res.get("unknown") else 0


if __name__ == "__main__":
    sys.exit(main())
