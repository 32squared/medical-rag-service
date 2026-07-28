"""synonym_expander 단위 테스트 — DB/네트워크 불필요."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import synonym_expander
from synonym_expander import expand_tokens, reload_synonyms


def setup_module(module):
    reload_synonyms()


def test_expand_basic_layman_to_medical():
    """일반인 표현 → 의학 용어 확장 ('속쓰림' 그룹)."""
    out = expand_tokens(["속쓰림"])
    assert "속쓰림" in out
    assert "위산역류" in out


def test_expand_medical_to_layman():
    """역방향 확장 ('현훈' → '어지러움')."""
    out = expand_tokens(["현훈"])
    assert "어지러움" in out or "어지럼증" in out


def test_original_tokens_preserved_in_order():
    """원본 토큰이 순서대로 앞에 유지된다 (ILIKE 랭킹 가중)."""
    tokens = ["발열", "기침"]
    out = expand_tokens(tokens)
    assert out[:2] == tokens


def test_no_duplicates():
    out = expand_tokens(["어지러움", "어지럼증"])
    normalized = [t.replace(" ", "").lower() for t in out]
    assert len(normalized) == len(set(normalized))


def test_max_total_cap():
    """확장 후 토큰 수 상한 준수 (tsquery 폭발 방지)."""
    tokens = ["속쓰림", "어지러움", "두통", "복통", "발열", "기침"]
    out = expand_tokens(tokens, max_total=10)
    assert len(out) <= 10


def test_unknown_token_passthrough():
    out = expand_tokens(["존재하지않는단어xyz"])
    assert out == ["존재하지않는단어xyz"]


def test_empty_input():
    assert expand_tokens([]) == []


def test_missing_file_graceful(monkeypatch):
    """사전 파일이 없어도 원본 토큰 그대로 반환 (무해 폴백)."""
    monkeypatch.setattr(synonym_expander, "_SYNONYMS_FILENAME", "no_such_file.json")
    synonym_expander._INDEX = {}
    synonym_expander._LOADED = False
    out = expand_tokens(["속쓰림"])
    assert out == ["속쓰림"]
    # 원상 복구
    monkeypatch.setattr(synonym_expander, "_SYNONYMS_FILENAME", "medical_synonyms.json")
    reload_synonyms()


def test_reload_returns_index_size():
    n = reload_synonyms()
    assert n > 100  # 90+ 그룹 × 평균 2개 이상 term
