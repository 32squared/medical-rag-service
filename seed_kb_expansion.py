"""
seed_kb_expansion.py — KB 확장 P1~P6 시드 일괄 실행 오케스트레이터.

신규 시드 5종을 순차 실행한다 (각 시드는 멱등 — upsert=True):
  1. seed_reference_ranges  — 참조범위 구조화 테이블 + KB 문서 (P2)
  2. seed_vaccination_kb    — 국가예방접종 NIP (P1-1)
  3. seed_navigation_kb     — 진료과·응급실·건강보험·검진 안내 (P4 + P1-2)
  4. seed_lifecycle_kb      — 암·정신건강·임신·노인·희귀·만성질환 (P3)
  5. seed_safety_kb         — 중독·소아 응급 (P6)

실행:
  python seed_kb_expansion.py            # 전체 적재
  python seed_kb_expansion.py --dry-run  # 빌드 검증만

Cloud Run Job:
  .\\deploy-kb-seed.ps1 -Script seed_kb_expansion.py -Execute
선행조건: migrations/migrate_runner.py --sync (010 vital_reference_ranges)
"""

from __future__ import annotations

import argparse
import io
import sys

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="KB 확장 P1~P6 시드 일괄 실행")
    ap.add_argument("--dry-run", action="store_true")
    # deploy-kb-seed.ps1 -Upsert 호환 — 확장 시드는 내부적으로 항상 upsert=True
    ap.add_argument("--upsert", action="store_true", help="호환용 (항상 upsert)")
    args = ap.parse_args()

    from seed_reference_ranges import seed_reference_ranges
    from seed_vaccination_kb import seed_vaccination_kb
    from seed_navigation_kb import seed_navigation_kb
    from seed_lifecycle_kb import seed_lifecycle_kb
    from seed_safety_kb import seed_safety_kb

    seeds = [
        ("reference_ranges", seed_reference_ranges),
        ("vaccination", seed_vaccination_kb),
        ("navigation", seed_navigation_kb),
        ("lifecycle", seed_lifecycle_kb),
        ("safety", seed_safety_kb),
    ]

    failed = []
    for name, fn in seeds:
        print(f"\n=== [{name}] 시작 ===", flush=True)
        try:
            summary = fn(dry_run=args.dry_run)
            print(f"=== [{name}] 완료: {summary}", flush=True)
            if not args.dry_run and summary.get("ingested", 0) == 0:
                failed.append(name)
        except Exception as e:
            print(f"=== [{name}] 실패: {e}", flush=True)
            failed.append(name)

    if failed:
        print(f"\n[seed_kb_expansion] 실패/0건 적재 시드: {failed}", flush=True)
        sys.exit(1)
    print("\n[seed_kb_expansion] 전체 완료", flush=True)


if __name__ == "__main__":
    main()
