"""seed_reference_ranges 빌더 단위 테스트 — DB/네트워크 불필요."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_reference_ranges import (
    _RANGES,
    build_cross_reference_documents,
    build_reference_documents,
    build_reference_rows,
)
from vital_rules import _CROSS_WHITELIST


def test_rows_have_unique_ids():
    rows = build_reference_rows()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert len(rows) >= 10


def test_every_row_has_official_source():
    """전 구간에 공식 출처 명기 — 마스터플랜 P1 원칙."""
    for row in build_reference_rows():
        assert row["source_name"], f"{row['id']}: source_name 누락"
        assert row["unit"], f"{row['id']}: unit 누락"


def test_ranges_json_parses():
    for row in build_reference_rows():
        parsed = json.loads(row["ranges_json"])
        assert isinstance(parsed, list) and parsed, f"{row['id']}: ranges 비어있음"
        for rng in parsed:
            assert rng.get("label") and rng.get("rule"), f"{row['id']}: 구간 정의 불완전"


def test_locale_separation_for_bp():
    """혈압은 KR(KSH)/US(ACC-AHA) 로케일 분리 — 기준 상이 반영."""
    rows = build_reference_rows()
    bp_locales = {r["locale"] for r in rows if r["signal_key"] == "blood_pressure"}
    assert {"KR", "US"} <= bp_locales


def test_documents_one_per_signal():
    docs = build_reference_documents()
    signals = {r["signal_key"] for r in _RANGES}
    assert len(docs) == len(signals)


def test_documents_contain_disclaimer():
    """모든 문서에 '진단은 의료기관' 안내 포함 (의료법 안전 문구)."""
    for doc in build_reference_documents():
        assert "의료기관" in doc["content_md"], f"{doc['title']}: 안내 문구 누락"
        assert doc["source_id"] == "vital_refs"
        assert doc["metadata"]["evidence_level"] == "A"


def test_documents_no_diagnostic_phrasing():
    """문서 본문에 단정 진단 표현 금지."""
    forbidden = ["진단됩니다", "확진입니다", "병입니다"]
    for doc in build_reference_documents():
        for phrase in forbidden:
            assert phrase not in doc["content_md"], (
                f"{doc['title']}: 금지 표현 '{phrase}' 포함"
            )


# ── 교차신호 근거 KB + cite_doc_id 별칭 (11 §5 / I9 evidence_required) ──

def test_band_docs_have_cite_doc_id_alias():
    """밴드 문서는 finding 조인용 불변 별칭(metadata.cite_doc_id)을 가짐(11 §5)."""
    for doc in build_reference_documents():
        assert doc["metadata"].get("cite_doc_id"), f"{doc['title']}: cite_doc_id 별칭 누락"


def test_cross_doc_exists_for_metabolic_combo():
    cite_ids = {d["metadata"]["cite_doc_id"] for d in build_cross_reference_documents()}
    assert "ref.metabolic.kr" in cite_ids


def test_cross_docs_population_level_and_safe():
    for d in build_cross_reference_documents():
        md = d["content_md"]
        assert "의료기관" in md  # 디스클레이머(의료법 안전 문구)
        for bad in ("진단됩니다", "확진입니다", "당신은", "귀하는"):
            assert bad not in md, f"{d['title']}: 개인귀속/진단 표현 '{bad}'"


def test_every_non_wellness_combo_has_evidence_doc():
    """I9 evidence_required: 비-웰니스 조합의 cite_doc_id는 실제 KB 문서로 해소돼야 함."""
    doc_ids = {d["metadata"]["cite_doc_id"] for d in build_cross_reference_documents()}
    for combo in _CROSS_WHITELIST:
        if combo.get("wellness_only"):
            continue
        cid = combo.get("cite_doc_id")
        assert cid and cid in doc_ids, f"{combo['combo_id']}: 근거 문서 없음(I9 위반)"
