"""KB 확장 시드 빌더(P1/P3/P4/P6) 통합 단위 테스트 — DB/네트워크 불필요.

각 빌더가 ingest 가능한 문서 구조를 반환하고, 의료법 안전 문구 원칙
(안심 단정 금지, 명령형 처방 금지)을 지키는지 검증한다.
ComplianceAnalyzer가 사용 가능하면 CRITICAL 위반 0건도 확인한다.
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_vaccination_kb import build_vaccination_documents
from seed_navigation_kb import build_navigation_documents
from seed_lifecycle_kb import build_lifecycle_documents
from seed_safety_kb import build_safety_documents

_ALL_BUILDERS = [
    ("vaccination", build_vaccination_documents, "nip", 5),
    ("navigation", build_navigation_documents, "navigation_kr", 5),
    ("lifecycle", build_lifecycle_documents, "lifecycle_kr", 12),
    ("safety", build_safety_documents, "safety_kr", 5),
]

# 안심 단정·처방 지시 금지 표현 (시스템 가드레일 원칙과 동일 방향)
_FORBIDDEN_PHRASES = [
    "괜찮습니다",          # 안심 단정
    "병원 안 가도",        # 진료 불필요 단정
    "응급이 아닙니다",      # 응급 부정 단정
    "복용하세요",          # 명령형 복약 지시 (상담 권유는 허용)
    "드시면 안 됩니다",     # 명령형 복약 금지 지시
]


@pytest.mark.parametrize("name,builder,source_id,min_docs", _ALL_BUILDERS)
def test_builder_returns_valid_documents(name, builder, source_id, min_docs):
    docs = builder()
    assert len(docs) >= min_docs, f"{name}: 문서 수 부족 ({len(docs)} < {min_docs})"
    keys = set()
    for d in docs:
        assert d["title"], f"{name}: title 누락"
        assert len(d["content_md"]) > 200, f"{name}/{d['title']}: 본문 너무 짧음"
        assert d["source_id"] == source_id
        assert d["evidence_topic"], f"{name}/{d['title']}: evidence_topic 누락"
        assert d["topic_keywords"], f"{name}/{d['title']}: topic_keywords 누락"
        assert d["metadata"].get("evidence_level") in ("A", "B")
        key = d["metadata"].get("doc_key")
        assert key and key not in keys, f"{name}: doc_key 중복/누락 ({key})"
        keys.add(key)


@pytest.mark.parametrize("name,builder,source_id,min_docs", _ALL_BUILDERS)
def test_no_forbidden_phrases(name, builder, source_id, min_docs):
    """안심 단정·명령형 지시 금지 (보수 방향 단정만 허용 원칙)."""
    for d in builder():
        for phrase in _FORBIDDEN_PHRASES:
            assert phrase not in d["content_md"], (
                f"{name}/{d['title']}: 금지 표현 '{phrase}' 포함"
            )


@pytest.mark.parametrize("name,builder,source_id,min_docs", _ALL_BUILDERS)
def test_emergency_paths_present_where_expected(name, builder, source_id, min_docs):
    """안전 영역 문서는 119/응급 연계 문구를 포함해야 한다."""
    if name != "safety":
        return
    for d in builder():
        assert "119" in d["content_md"] or "응급실" in d["content_md"], (
            f"{name}/{d['title']}: 응급 연계 문구 누락"
        )


def test_build_drug_info_md():
    """e약은요(P1-3) 마크다운 빌더 — 섹션 구성 + 상담 안내 문구."""
    from collect_public_kb import build_drug_info_md

    item = {
        "itemName": "테스트정",
        "entpName": "테스트제약",
        "efcyQesitm": "이 약은 두통, 발열의 완화에 사용합니다.",
        "useMethodQesitm": "<p>성인 1회 1정</p>",
        "atpnQesitm": "임부 또는 임신 가능성이 있는 여성은 복용 전 상의하십시오.",
    }
    md = build_drug_info_md(item)
    assert "테스트정" in md
    assert "## 효능" in md
    assert "<p>" not in md          # HTML 태그 제거
    assert "의사·약사와 상담" in md   # 상담 안내 의무 문구


def test_kb_content_precheck_passes():
    """수집 파이프라인의 정보성 KB 게이트(precheck_violations, kb_content 컨텍스트)를
    전 문서가 통과해야 한다 — collect_public_kb 적재 정책과 동일 기준."""
    try:
        from collect_public_kb import precheck_violations
    except Exception:
        pytest.skip("collect_public_kb 의존성 사용 불가")

    for name, builder, _sid, _n in _ALL_BUILDERS:
        for d in builder():
            violations = precheck_violations(d["content_md"], source_id=d["source_id"])
            assert not violations, f"{name}/{d['title']}: KB 게재 부적합 {violations}"


# ── 시드 문서 식별 — 기관 대표 URL 공유 ─────────────────────────────────
# 시드 문서들은 기관 대표 URL 을 같이 쓴다. ingest 가 URL 을 정규화하며 '#key' 를 지워
# URL 로 식별하면 같은 출처 문서들이 서로를 덮는다(dev 실측: '공복혈당' 행에 HbA1c 본문,
# HbA1c·PM10 행 없음). 그래서 시드는 match_url=False 로 제목을 식별자로 쓴다.
_SEED_MODULES = [
    "seed_reference_ranges", "seed_vaccination_kb", "seed_navigation_kb",
    "seed_lifecycle_kb", "seed_safety_kb",
]


def _run_seed_capturing_ingest(mod_name, monkeypatch):
    import kb_ingest
    mod = importlib.import_module(mod_name)
    calls = []
    monkeypatch.setattr(mod, "_register_source", lambda: None)
    if hasattr(mod, "insert_reference_rows"):
        monkeypatch.setattr(mod, "insert_reference_rows", lambda rows: 0)
    monkeypatch.setattr(kb_ingest, "ingest_document",
                        lambda **kw: calls.append(kw) or {"status": "inserted"})
    summary = getattr(mod, mod_name)(dry_run=False)
    return calls, summary


@pytest.mark.parametrize("mod_name", _SEED_MODULES)
def test_seed_identifies_docs_by_title(mod_name, monkeypatch):
    calls, summary = _run_seed_capturing_ingest(mod_name, monkeypatch)
    assert calls and summary["ingested"] == len(calls)
    assert all(c.get("match_url") is False for c in calls), f"{mod_name}: match_url=False 누락"
    keys = [(c["source_id"], c["title"]) for c in calls]
    assert len(keys) == len(set(keys)), f"{mod_name}: 출처 안 제목 중복 — 제목이 식별자"


def test_reference_seed_ingests_cross_docs(monkeypatch):
    """교차조합 근거 문서(vital_rules._CROSS_WHITELIST 의 cite_doc_id)도 적재한다."""
    from vital_rules import _CROSS_WHITELIST
    calls, _ = _run_seed_capturing_ingest("seed_reference_ranges", monkeypatch)
    cited = {c["metadata"].get("cite_doc_id") for c in calls}
    for combo in _CROSS_WHITELIST:
        if combo.get("cite_doc_id"):
            assert combo["cite_doc_id"] in cited
