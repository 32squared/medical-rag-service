"""골든셋 오프라인 평가 회귀 게이트 (CI). DB/LLM 불필요.

베이스라인을 잠그고 ratchet-up 한다. 안전 게이트(응급/위기)는 100% 필수.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from eval_harness import run_eval


@pytest.fixture(scope="module")
def report():
    from synonym_expander import reload_synonyms
    from symptom_catalog import reload_catalog
    from symptom_matcher import reload_matcher
    reload_synonyms()
    reload_catalog()
    reload_matcher()
    return run_eval()


def test_safety_gate_perfect(report):
    """응급/위기 분류는 안전 직결 — 100% 미만이면 실패(절대 회귀 불가)."""
    d = report["summary"]["safety"]
    assert d["rate"] == 1.0, f"안전 게이트 회귀: {d['pass']}/{d['total']}"


def test_colloquial_reach_baseline(report):
    """구어체 증상 도달률 — 현재 1.0, 0.85 미만이면 회귀."""
    rate = report["summary"]["reach_colloquial"]["rate"]
    assert rate >= 0.85, f"구어체 도달률 회귀: {rate:.2%}"


def test_symptom_reach_baseline(report):
    rate = report["summary"]["symptom"]["rate"]
    assert rate >= 0.90, f"증상 도달 회귀: {rate:.2%}"


def test_department_baseline(report):
    rate = report["summary"]["department"]["rate"]
    assert rate >= 0.90, f"진료과 일치 회귀: {rate:.2%}"


def test_intent_baseline(report):
    """오프라인 규칙기반 intent — 정보용, 0.85 하한."""
    rate = report["summary"]["intent"]["rate"]
    assert rate >= 0.85, f"intent 회귀: {rate:.2%}"
