"""archetype_stats.py — 월간 희귀도 배치(spec-03 §5-3). 사용자 단위 분포를 archetype_monthly_stat 에 기록한다.

실행: python scripts/archetype_stats.py [YYYY-MM]   (기본: 이번 달, KST)
Cloud Run job 으로 1일 1회(KST 04:00) 돌린다. 분모 < 100 이면 API 가 rarity 를 숨기므로 값 자체는 항상 기록한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metrics_repo as mr  # noqa: E402
from routine_repo import today_kst  # noqa: E402


def main() -> int:
    month = (sys.argv[1] if len(sys.argv) > 1 else today_kst()[:7])
    out = mr.recompute_monthly_stats(month)
    for aid, v in sorted(out.items()):
        print(f"{month} {aid}: {v['user_count']}/{v['denominator']}")
    if not out:
        print(f"{month}: no archetype results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
