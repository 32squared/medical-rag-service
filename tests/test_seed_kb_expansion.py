"""KB 확장 시드 빌더(P1/P3/P4/P6) 통합 단위 테스트 — DB/네트워크 불필요.

각 빌더가 ingest 가능한 문서 구조를 반환하고, 의료법 안전 문구 원칙
(안심 단정 금지, 명령형 처방 금지)을 지키는지 검증한다.
ComplianceAnalyzer가 사용 가능하면 CRITICAL 위반 0건도 확인한다.
"""

import importlib
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_vaccination_kb import build_vaccination_documents
from seed_navigation_kb import build_navigation_documents
from seed_lifecycle_kb import build_lifecycle_documents
from seed_safety_kb import build_safety_documents
from seed_checkup_criteria_kb import build_checkup_documents

_ALL_BUILDERS = [
    ("vaccination", build_vaccination_documents, "nip", 5),
    ("navigation", build_navigation_documents, "navigation_kr", 5),
    ("lifecycle", build_lifecycle_documents, "lifecycle_kr", 12),
    ("safety", build_safety_documents, "safety_kr", 5),
    ("checkup_criteria", build_checkup_documents, "checkup_std_kr", 8),
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
    "seed_lifecycle_kb", "seed_safety_kb", "seed_checkup_criteria_kb",
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


# ── 검진 판정기준 — 개인 구간 분류 금지 항목·주제 라벨 ───────────────────
# vital_rules.PERSONAL_BAND_DENY 항목은 기준 수치를 싣지 않는다(개인 구간 분류 금지와 같은 방향).
# 새 deny 항목이 생기면 KB 에서 부르는 이름을 여기 더한다.
_DENY_TERMS = {
    "ldl_cholesterol": ("LDL", "저밀도"),
    "egfr": ("eGFR", "사구체여과율"),
    "bmd_tscore": ("골밀도", "T-점수", "T-score"),
    "urine_protein_dipstick": ("요단백",),
}


def test_checkup_docs_have_no_cutoffs_for_deny_items():
    from vital_rules import PERSONAL_BAND_DENY
    missing = set(PERSONAL_BAND_DENY) - set(_DENY_TERMS)
    assert not missing, f"새 deny 항목의 KB 표현을 _DENY_TERMS 에 추가: {missing}"
    terms = [t for ts in _DENY_TERMS.values() for t in ts]
    for d in build_checkup_documents():
        for sent in re.split(r"(?<=[.:])\s+|\n", d["content_md"]):
            if any(t in sent for t in terms):
                assert not re.search(r"\d", sent), f"{d['title']}: deny 항목 문장에 수치 — {sent}"


def test_checkup_deny_line_follows_vital_rules():
    from vital_rules import PERSONAL_BAND_DENY
    overview = build_checkup_documents()[0]["content_md"]
    for name in PERSONAL_BAND_DENY.values():
        assert name in overview


def test_checkup_topics_are_korean():
    """근거 게이트는 evidence_topic 문자열을 질의와 임베딩 비교한다 — 영문 snake_case 는
    한국어 질의와 0.13~0.15 로 문턱(0.30)을 넘지 못해 한국어 낱말로 쓴다."""
    for d in build_checkup_documents():
        assert re.search(r"[가-힣]", d["evidence_topic"]), d["evidence_topic"]
        assert "_" not in d["evidence_topic"]


def test_checkup_item_docs_do_not_tie_band_to_need():
    """항목 문서는 판정 구분에 '필요한 구간' 같은 판단을 붙이지 않는다 — 적재 뒤 PHR 답이
    "두 값 모두 정상B(경계)에 해당하므로 … 필요한 구간으로 안내됩니다"로 옮겼다(dev rev 00061).
    판정 구분의 뜻은 개요 문서(고시 정의)에만 둔다."""
    for d in build_checkup_documents()[1:]:
        for sent in re.split(r"(?<=[.])\s+|\n", d["content_md"]):
            assert not ("정상B" in sent and "필요" in sent), f"{d['title']}: {sent}"


def test_checkup_footer_points_to_result_sheet():
    """개인의 판정은 결과통보서의 판정 — 모든 문서의 마지막 청크(꼬리말)에 들어간다."""
    for d in build_checkup_documents():
        assert "결과통보서에 적힌 판정" in d["content_md"].rsplit("\n\n", 1)[-1]


def test_checkup_chunks_fit_prompt_window():
    """프롬프트는 청크 본문을 500자에서 자른다 — 넘치면 꼬리말(출처·판정 안내)이 잘린다."""
    from kb_ingest import chunk_markdown
    for d in build_checkup_documents():
        for c in chunk_markdown(d["content_md"]):
            body = c["content"] if isinstance(c, dict) else getattr(c, "content", str(c))
            assert len(body) < 500, f"{d['title']}: {len(body)}자"
