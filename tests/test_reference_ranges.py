"""seed_reference_ranges 빌더 단위 테스트 — DB/네트워크 불필요."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_reference_ranges import (
    _RANGES,
    build_reference_documents,
    build_reference_rows,
)


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
