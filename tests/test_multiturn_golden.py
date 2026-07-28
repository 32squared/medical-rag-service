"""
멀티턴 골든셋 회귀 게이트 (06-multiturn-design.md §8).

착수 게이트: 규칙 재작성만으로 후속질의 standalone화 정확도 ≥80%.
대화 시퀀스(직전 주제 → 후속질의 → 기대 재작성)를 골든셋으로 고정해 회귀를 막는다.
"""

import json
from pathlib import Path

from followup_rewriter import is_followup, rewrite_followup

_GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "multiturn_golden.json").read_text(encoding="utf-8")
)

_ACCURACY_GATE = 0.80


def test_rewrite_accuracy_meets_gate():
    """규칙 재작성 정확도(method+contains 동시 일치)가 게이트(≥80%)를 넘어야 한다."""
    cases = _GOLDEN["rewrite_cases"]
    ok = 0
    misses = []
    for c in cases:
        out, method = rewrite_followup(c["followup"], c["last_symptom"])
        if method == c["method"] and c["contains"] in out:
            ok += 1
        else:
            misses.append((c["followup"], method, out))
    accuracy = ok / len(cases)
    assert accuracy >= _ACCURACY_GATE, (
        f"재작성 정확도 {accuracy:.0%} < {_ACCURACY_GATE:.0%}. 미스: {misses}"
    )


def test_followup_detection_on_rewrite_cases():
    """재작성 케이스는 turn>0·증상0건일 때 후속으로 탐지되어야 한다."""
    misses = [
        c["followup"] for c in _GOLDEN["rewrite_cases"]
        if not is_followup(c["followup"], turn_count=1, current_symptom_keys=[])
    ]
    # 탐지율도 게이트 적용(대명사 일부는 신호 없을 수 있어 ≥80%)
    detected = len(_GOLDEN["rewrite_cases"]) - len(misses)
    assert detected / len(_GOLDEN["rewrite_cases"]) >= _ACCURACY_GATE, \
        f"후속 탐지 미스: {misses}"


def test_no_rewrite_cases_stay_original():
    """후속 신호가 없는 발화는 재작성되지 않아야 한다(오재작성 방지)."""
    for c in _GOLDEN["no_rewrite_cases"]:
        out, method = rewrite_followup(c["followup"], c["last_symptom"])
        assert method == "none", f"오재작성: {c['followup']} → {out}"
