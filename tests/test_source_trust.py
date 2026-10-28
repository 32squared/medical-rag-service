"""
source_trust — 공인 기관 출처만 검색하는 모드 단위 테스트 (DB·네트워크 불필요).

  1. 등록부: 실제 DB 에 있는 출처 id 가 모두 분류돼 있고, 신뢰 집합이 기대와 같다
  2. restrict_source_types: 모드 on/off, 교집합, 빈 결과
  3. hybrid_search: 신뢰 출처 밖 요청은 검색 생략([]), None 이면 신뢰 목록으로 검색
  4. 프롬프트·인용·Evidence Pack 의 출처 표기가 기관명이다
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import source_trust as st


# 2026-10-28 dev·운영 kb_sources 에 등록된 id (docs/plan/29 §1)
_DB_SOURCE_IDS = [
    "health_kdca", "consultation_seed", "mfds_dur", "consultation_checklist", "nemc",
    "guideline_internal", "checkup_std_kr", "lifecycle_kr", "vital_refs", "nip",
    "safety_kr", "navigation_kr", "kr_law", "gpt_generated_v1", "kdca_api", "mfds",
    "kmle_seed", "hira_kdca", "internal_md",
]

_EXPECTED_TRUSTED_IN_DB = {
    "health_kdca", "mfds_dur", "nemc", "checkup_std_kr", "kr_law", "kdca_api", "mfds", "hira_kdca",
}


@pytest.fixture
def mode_on(monkeypatch):
    monkeypatch.setenv("RAG_TRUSTED_SOURCES_ONLY", "1")


@pytest.fixture
def mode_off(monkeypatch):
    monkeypatch.setenv("RAG_TRUSTED_SOURCES_ONLY", "0")


# ── 1. 등록부 ────────────────────────────────────────────────

def test_every_db_source_is_classified():
    missing = [s for s in _DB_SOURCE_IDS if st.provenance_of(s) == st.UNKNOWN]
    assert missing == []


def test_trusted_set_matches_expectation():
    trusted = {s for s in _DB_SOURCE_IDS if st.is_trusted_source(s)}
    assert trusted == _EXPECTED_TRUSTED_IN_DB


def test_self_authored_and_curated_are_excluded():
    for sid in ("consultation_seed", "consultation_checklist", "lifecycle_kr", "vital_refs",
                "nip", "safety_kr", "navigation_kr", "guideline_internal", "gpt_generated_v1",
                "pubmed", "kmle_seed"):
        assert not st.is_trusted_source(sid), sid


def test_unknown_source_is_not_trusted():
    assert st.provenance_of("brand_new_source") == st.UNKNOWN
    assert not st.is_trusted_source("brand_new_source")
    assert st.source_display_name("brand_new_source") == "brand_new_source"


def test_display_names_are_institution_names():
    assert st.source_display_name("health_kdca") == "질병관리청 국가건강정보포털"
    assert st.source_display_name("mfds_dur").startswith("식품의약품안전처")
    assert st.source_jurisdiction("cdc_mmwr") == "US"
    assert st.source_jurisdiction("health_kdca") == "KR"


def test_default_mode_is_on(monkeypatch):
    monkeypatch.delenv("RAG_TRUSTED_SOURCES_ONLY", raising=False)
    assert st.trusted_sources_only() is True
    for v in ("0", "false", "off", "No"):
        monkeypatch.setenv("RAG_TRUSTED_SOURCES_ONLY", v)
        assert st.trusted_sources_only() is False


# ── 2. restrict_source_types ────────────────────────────────

def test_restrict_none_gives_trusted_list(mode_on):
    out = st.restrict_source_types(None)
    assert out == st.trusted_source_ids()
    assert "health_kdca" in out and "consultation_seed" not in out


def test_restrict_intersects(mode_on):
    assert st.restrict_source_types(["consultation_seed", "nemc", "x"]) == ["nemc"]


def test_restrict_empty_when_nothing_trusted(mode_on):
    assert st.restrict_source_types(["consultation_seed", "lifecycle_kr"]) == []


def test_restrict_passthrough_when_off(mode_off):
    assert st.restrict_source_types(None) is None
    assert st.restrict_source_types(["consultation_seed"]) == ["consultation_seed"]


def test_describe_shape(mode_on):
    d = st.describe()
    assert d["trusted_sources_only"] is True
    assert set(d["trusted_source_ids"]).isdisjoint(d["excluded_source_ids"])
    assert d["provenance"]["checkup_std_kr"] == st.OFFICIAL_RECORD


# ── 3. hybrid_search 연결 ───────────────────────────────────

def _chunk(cid, source_id="health_kdca"):
    return {
        "chunk_id": cid, "document_id": f"d_{cid}", "content": "내용", "section_path": [],
        "symptom_tags": "[]", "severity": None, "evidence_country": "KR",
        "regulatory_korea": False, "evidence_topic": None, "topic_keywords": "[]",
        "source_id": source_id, "evidence_level": "A", "title": "t", "score": 0.5,
        "boost_reasons": [],
    }


def test_hybrid_search_skips_when_requested_sources_untrusted(mode_on):
    from rag_engine import hybrid_search
    with patch("rag_engine._is_postgres", return_value=True), \
         patch("rag_engine._get_embedding_provider") as mock_ep, \
         patch("rag_engine._dense_search") as dense, \
         patch("rag_engine._sparse_search") as sparse:
        mock_ep.return_value.embed.return_value = [[0.1] * 1536]
        out = hybrid_search("두통", top_k=3, source_types=["consultation_seed"],
                            enable_evidence_topic_check=False)
    assert out == []
    dense.assert_not_called()
    sparse.assert_not_called()


def test_hybrid_search_passes_trusted_list_when_unfiltered(mode_on):
    from rag_engine import hybrid_search
    with patch("rag_engine._is_postgres", return_value=True), \
         patch("rag_engine._get_embedding_provider") as mock_ep, \
         patch("rag_engine._dense_search", return_value=[_chunk("A")]) as dense, \
         patch("rag_engine._sparse_search", return_value=[]) as sparse:
        mock_ep.return_value.embed.return_value = [[0.1] * 1536]
        out = hybrid_search("두통", top_k=3, enable_evidence_topic_check=False)
    assert [c["chunk_id"] for c in out] == ["A"]
    passed = dense.call_args[0][1]
    assert passed == st.trusted_source_ids()
    assert sparse.call_args[0][1] == st.trusted_source_ids()


def test_hybrid_search_unfiltered_when_mode_off(mode_off):
    from rag_engine import hybrid_search
    with patch("rag_engine._is_postgres", return_value=True), \
         patch("rag_engine._get_embedding_provider") as mock_ep, \
         patch("rag_engine._dense_search", return_value=[]) as dense, \
         patch("rag_engine._sparse_search", return_value=[]):
        mock_ep.return_value.embed.return_value = [[0.1] * 1536]
        hybrid_search("두통", top_k=3, enable_evidence_topic_check=False)
    assert dense.call_args[0][1] is None


# ── 4. 출처 표기 ────────────────────────────────────────────

def test_user_prompt_shows_institution_name():
    from rag_engine import _build_rag_user_prompt
    text = _build_rag_user_prompt("두통", [_chunk("A", "health_kdca")])
    assert "출처: 질병관리청 국가건강정보포털" in text
    assert "출처: health_kdca" not in text


def test_citations_carry_source_name():
    from rag_engine import _extract_citations
    cites = _extract_citations("답 [1]", [_chunk("A", "mfds_dur")])
    assert cites[0]["source_id"] == "mfds_dur"
    assert cites[0]["source_name"].startswith("식품의약품안전처")


def test_evidence_pack_uses_institution_name():
    from evidence_pack import build_evidence_pack, render_evidence_for_prompt
    pack = build_evidence_pack("두통", {"intent": "general_health"},
                               [_chunk("A", "nemc"), _chunk("B", "cdc_mmwr")])
    names = {it["source_id"]: it for it in pack["evidence_items"]}
    assert names["nemc"]["source_name"].startswith("중앙응급의료센터")
    assert names["cdc_mmwr"]["jurisdiction"] == "US"
    assert any("해외" in lim for lim in names["cdc_mmwr"]["limitations"])
    assert "출처: 중앙응급의료센터" in render_evidence_for_prompt(pack)
