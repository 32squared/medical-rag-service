"""
eval_harness.py — 골든셋 오프라인 평가 하니스 (Sprint 1 측정 기반).

DB/LLM/네트워크 없이 측정 가능한 차원만 평가한다:
  - 증상 도달(symptom reach): match_symptoms 결과에 기대 symptom_key 포함 여부
  - 진료과(department): department_hint 첫 진료과 일치
  - intent: classify_question(오프라인 규칙기반) 일치 — 정보용
  - 안전 게이트(safety): process_medical_query safety_level (emergency/crisis)

"평가가 수집을 견인" 원칙의 측정 도구. 검색 recall/faithfulness 등 DB 필요한
차원은 별도 라이브 하니스(tests/auto_validate_rag.py)에서 다룬다.

실행:
  python eval_harness.py                  # 리포트 출력
  python eval_harness.py --json           # JSON 결과
  python eval_harness.py --fail-under 0.75  # 도달률 게이트 (CI)

run_eval()은 순수 측정 — pytest에서도 import해 사용(tests/test_golden_eval.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

_REPO = os.path.dirname(os.path.abspath(__file__))
_GOLDEN_PATH = os.path.join(_REPO, "tests", "golden", "golden_set.json")


def _load_cases(path: str = _GOLDEN_PATH) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", [])


def run_eval(cases: List[Dict] = None) -> Dict:
    """골든셋 평가 → 차원별 지표 + 케이스별 결과 (순수 측정)."""
    if cases is None:
        cases = _load_cases()

    from symptom_matcher import match_symptoms, department_hint

    # process_medical_query / classify는 무거우므로 필요한 케이스에만 호출
    def _classify(q):
        from medical_classifier import classify_question
        return classify_question(q)

    def _safety(q):
        from medical_rag_pipeline import process_medical_query
        return process_medical_query(q)["safety_level"]

    dims = {
        "symptom": {"total": 0, "pass": 0},
        "department": {"total": 0, "pass": 0},
        "intent": {"total": 0, "pass": 0},
        "safety": {"total": 0, "pass": 0},
        "reach_colloquial": {"total": 0, "pass": 0},
    }
    results = []

    for c in cases:
        q = c["query"]
        row = {"id": c.get("id"), "query": q, "checks": {}}
        matched = match_symptoms(q)

        # 증상 도달
        if "expect_symptom" in c:
            exp = c["expect_symptom"]
            dims["symptom"]["total"] += 1
            if exp is None:
                ok = (len(matched) == 0)
            else:
                ok = exp in matched
            dims["symptom"]["pass"] += int(ok)
            row["checks"]["symptom"] = {"expect": exp, "got": matched, "pass": ok}
            # 구어체 도달률 (expect_symptom이 실제 증상인 케이스만)
            if c.get("colloquial") and exp:
                dims["reach_colloquial"]["total"] += 1
                dims["reach_colloquial"]["pass"] += int(bool(matched))

        # 진료과
        if "expect_department" in c:
            exp = c["expect_department"]
            got = department_hint(q)["departments"]
            ok = bool(got) and got[0] == exp
            dims["department"]["total"] += 1
            dims["department"]["pass"] += int(ok)
            row["checks"]["department"] = {"expect": exp, "got": got, "pass": ok}

        # intent (오프라인 규칙기반 — 정보용)
        if "expect_intent" in c:
            got = _classify(q).get("intent")
            ok = got == c["expect_intent"]
            dims["intent"]["total"] += 1
            dims["intent"]["pass"] += int(ok)
            row["checks"]["intent"] = {"expect": c["expect_intent"], "got": got, "pass": ok}

        # 안전 게이트 (critical)
        if "expect_safety" in c:
            got = _safety(q)
            ok = got == c["expect_safety"]
            dims["safety"]["total"] += 1
            dims["safety"]["pass"] += int(ok)
            row["checks"]["safety"] = {"expect": c["expect_safety"], "got": got, "pass": ok}

        results.append(row)

    def _rate(d):
        return round(d["pass"] / d["total"], 4) if d["total"] else None

    summary = {dim: {"pass": v["pass"], "total": v["total"], "rate": _rate(v)}
               for dim, v in dims.items()}
    return {"summary": summary, "cases": len(cases), "results": results}


def _print_report(report: Dict) -> None:
    s = report["summary"]
    print("=" * 60)
    print(f"  골든셋 오프라인 평가 — {report['cases']}케이스")
    print("=" * 60)
    labels = {
        "symptom": "증상 도달",
        "department": "진료과 일치",
        "intent": "intent 일치(규칙기반)",
        "safety": "안전 게이트(응급/위기)",
        "reach_colloquial": "구어체 증상 도달률",
    }
    for dim, lab in labels.items():
        d = s[dim]
        if d["total"]:
            bar = "█" * int((d["rate"] or 0) * 20)
            print(f"  {lab:24} {d['pass']:3}/{d['total']:<3} {d['rate']:.0%}  {bar}")
    # 실패 케이스 표시
    fails = []
    for r in report["results"]:
        for dim, chk in r["checks"].items():
            if not chk["pass"]:
                fails.append(f"  ✗ [{dim}] {r['id']}: {r['query']!r} 기대={chk['expect']} 실제={chk['got']}")
    if fails:
        print("-" * 60)
        print(f"  실패 {len(fails)}건:")
        for line in fails[:40]:
            print(line)
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description="골든셋 오프라인 평가")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="구어체 증상 도달률 게이트 (미만이면 exit 1)")
    args = ap.parse_args()

    report = run_eval()
    if args.json:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    if args.fail_under is not None:
        rate = report["summary"]["reach_colloquial"]["rate"] or 0.0
        if rate < args.fail_under:
            print(f"[FAIL] 구어체 도달률 {rate:.2%} < 게이트 {args.fail_under:.2%}")
            sys.exit(1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
