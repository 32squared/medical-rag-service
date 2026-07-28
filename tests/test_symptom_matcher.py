"""symptom_matcher / symptom_catalog / korean_tokenizer 단위 테스트 — DB/네트워크 불필요."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from korean_tokenizer import tokenize, backend
from symptom_catalog import (
    load_catalog,
    department_for,
    all_departments,
    reload_catalog,
)
from symptom_matcher import (
    match_symptoms,
    departments_for,
    department_hint,
    reload_matcher,
)


def setup_module(module):
    reload_catalog()
    reload_matcher()


# ── 토크나이저 ──
def test_tokenize_returns_list():
    toks = tokenize("나 머리가 아파요")
    assert isinstance(toks, list)


def test_backend_is_known():
    assert backend() in ("kiwi", "heuristic")


def test_tokenize_empty():
    assert tokenize("") == []


# ── 카탈로그 ──
def test_catalog_includes_base_and_supplement():
    cat = load_catalog()
    assert "headache" in cat            # 기존 42증상
    assert "pediatric_fever" in cat     # 보강
    assert "toothache" in cat
    assert len(cat) >= 42 + 10


def test_department_for():
    assert department_for("headache") == "신경과"
    assert department_for("toothache") == "치과"
    assert department_for("pediatric_fever") == "소아청소년과"
    assert department_for("nonexistent") == ""


def test_supplement_adds_new_departments():
    depts = all_departments()
    # 보강으로 치과·소아청소년과·응급의학과·외과가 추가됨
    for d in ("치과", "소아청소년과"):
        assert d in depts


# ── 매처 (도달률 핵심) ──
def test_colloquial_attached_form_reaches_symptom():
    """'머리아파'(붙여쓴 구어체)가 두통에 도달 — 핵심 회귀 방지."""
    assert "headache" in match_symptoms("나 머리아파")


def test_spaced_colloquial_via_synonym():
    """'머리가 아파요' — 동의어 'X머리가아파' 형태로 substring 도달."""
    assert "headache" in match_symptoms("머리가 아파요")


def test_multiple_symptoms():
    keys = match_symptoms("열나고 기침해요")
    assert "fever" in keys and "cough" in keys


def test_supplement_symptom_reachable():
    assert "vomiting" in match_symptoms("토할것같아")
    assert "burn_injury" in match_symptoms("데였어요")


def test_no_false_match_on_unrelated():
    assert match_symptoms("오늘 날씨 좋네요") == []


def test_departments_for_dedup_order():
    keys = ["headache", "dizziness"]   # 둘 다 신경과
    assert departments_for(keys) == ["신경과"]


def test_department_hint_structure():
    h = department_hint("나 머리아파")
    assert h["symptom_keys"] == ["headache"]
    assert h["departments"] == ["신경과"]
    assert "신경과" in h["hint"]
    # 의료법 안전: 진료과 안내에 응급 우선 단서 포함
    assert "119" in h["hint"] or "응급" in h["hint"]


def test_department_hint_empty_for_unmatched():
    h = department_hint("환율이 궁금해요")
    assert h["departments"] == []
    assert h["hint"] == ""


def test_reach_rate_baseline():
    """구어체 도달률 베이스라인 잠금 (Sprint 1 측정값). ratchet-up 대상."""
    colloquial = [
        "나 머리아파", "머리가 아파요", "배아파서 죽겠어", "열나고 기침해요",
        "아기가 열이 나요", "아이 발진이 났어요", "데였어요", "코피가 안 멈춰",
        "토할것같아", "허리아파요", "얼굴이 부었어요", "입술이 부었어",
    ]
    hit = sum(1 for q in colloquial if match_symptoms(q))
    rate = hit / len(colloquial)
    # 현재 측정 ~0.92 — 0.75 미만으로 떨어지면 회귀로 간주
    assert rate >= 0.75, f"구어체 도달률 회귀: {rate:.2f} ({hit}/{len(colloquial)})"
