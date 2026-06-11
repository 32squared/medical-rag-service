"""rag_gap_analysis 커버리지 확장 수요 신호 테스트 (Sprint 2). DB 불필요."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_gap_analysis import aggregate_gaps


def _row(q, quality="insufficient", cj=None):
    return {"query_text": q, "evidence_quality": quality, "classification_json": cj}


def test_uncovered_demand_surfaces_unmatched_symptoms():
    """카탈로그에 없는 증상(무좀·발기부전)이 확장 수요 큐에 잡힌다."""
    rows = [
        _row("발기부전 약 정보"),
        _row("발기부전 치료법"),
        _row("손톱 무좀 어떻게 하나요"),
        _row("머리아파 죽겠어"),       # 두통 도달 → unmapped 아님
        _row("갑상선 정상수치", quality="high"),  # insufficient 아님
    ]
    r = aggregate_gaps(rows)
    demand_queries = [d["query"] for d in r["coverage_expansion_demand"]]
    assert any("발기부전" in q for q in demand_queries)
    assert any("무좀" in q for q in demand_queries)
    # 두통 도달 질의는 수요에 없어야
    assert not any("머리아파" in q for q in demand_queries)


def test_covered_symptom_not_in_demand():
    """매처가 도달하는 증상(무릎)은 unmapped 수요에 안 들어간다."""
    rows = [_row("무릎이 아파요"), _row("배아파서 죽겠어")]
    r = aggregate_gaps(rows)
    assert r["unmapped_insufficient"] == 0
    assert r["coverage_expansion_demand"] == []


def test_repeated_unmapped_query_counted():
    """반복되는 미커버 질의는 count로 우선순위화된다."""
    rows = [_row("발기부전 정보")] * 3 + [_row("탈모 치료")]
    r = aggregate_gaps(rows)
    top = r["coverage_expansion_demand"][0]
    assert top["count"] == 3
    assert "발기부전" in top["query"]


def test_backward_compat_keys_present():
    """기존 출력 키 유지 (호환)."""
    r = aggregate_gaps([_row("두통")])
    for k in ("total", "insufficient", "insufficient_rate", "by_quality",
              "by_intent_insufficient", "collection_priority", "unmapped_insufficient"):
        assert k in r
