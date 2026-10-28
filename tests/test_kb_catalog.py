"""kb_catalog — 카탈로그 정합성·상태 판정 (네트워크·DB 없음)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kb_catalog as kc
import source_trust as st
from kb_collect import fetchers

_REQUIRED = {"id", "institution", "access", "fetcher", "key_env", "license", "provenance",
             "cadence_days", "status", "match_url", "routes"}


def test_entries_have_required_fields_and_unique_ids():
    seen = set()
    for e in kc.CATALOG:
        missing = _REQUIRED - set(e)
        assert not missing, f"{e.get('id')} 누락: {missing}"
        assert e["id"] not in seen
        seen.add(e["id"])
        assert e["status"] in kc.HUMAN_STATUSES
        assert e["access"] in kc.ACCESS_VALUES
        assert e.get("content_kind") in ("prose", "codes", "stats")
        assert set(e["license"]) >= {"type", "verified_at", "verify_url", "note"}


def test_every_fetcher_is_registered():
    for e in kc.CATALOG:
        assert e["fetcher"] in fetchers.names(), e["id"]


def test_provenance_matches_source_trust_registry():
    """카탈로그 출처는 source_trust 등록부에 같은 provenance 로 있어야 신뢰 모드에서 검색된다."""
    for e in kc.CATALOG:
        if e["id"] == "shortlist":   # 묶음 항목 — 실제 출처는 kb_shortlist_sources 가 등록
            continue
        assert st.provenance_of(e["id"]) == e["provenance"], e["id"]
        assert st.is_trusted_source(e["id"]), f"{e['id']} 는 신뢰 출처여야 자동 구축 대상이 된다"


def test_openapi_entries_declare_key_env():
    for e in kc.CATALOG:
        if e["access"] in kc.KEYED_ACCESS:
            assert e["key_env"], e["id"]


def test_openapi_entries_without_endpoint_are_not_active():
    """url 미확인 OpenAPI 항목은 active 로 두면 조용히 not_implemented 만 쌓인다."""
    for e in kc.CATALOG:
        if e["fetcher"] == "datagokr_generic" and not (e.get("api") or {}).get("url"):
            assert e["status"] != kc.STATUS_ACTIVE, e["id"]


def test_effective_status_gates():
    entry = dict(kc.get("mfds_dur"))
    assert kc.effective_status(entry, env={}) == kc.STATUS_PENDING_KEY
    assert kc.effective_status(entry, env={"DATA_GO_KR_KEY": "k"}) == kc.STATUS_ACTIVE
    bad = dict(entry, license=dict(entry["license"], type="kogl_type4"))
    assert kc.effective_status(bad, env={"DATA_GO_KR_KEY": "k"}) == kc.STATUS_PENDING_LICENSE
    human = dict(entry, status=kc.STATUS_PENDING_VERIFY)
    assert kc.effective_status(human, env={"DATA_GO_KR_KEY": "k"}) == kc.STATUS_PENDING_VERIFY


def test_runnable_with_key_includes_dur_only_active():
    ids = {e["id"] for e in kc.runnable(env={"DATA_GO_KR_KEY": "k"})}
    assert "mfds_dur" in ids
    assert "health_kdca" not in ids     # 제4유형 — 라이선스 결정 대기
    assert "mfds" not in ids            # OpenAPI 전환 중(엔드포인트 미확인)
    assert "nhis_health_in" not in ids  # robots 차단


def test_status_table_explains_needs():
    rows = {r["id"]: r for r in kc.status_table(env={})}
    assert "DATA_GO_KR_KEY" in rows["mfds_dur"]["needs"]
    assert "라이선스" in rows["health_kdca"]["needs"]
    assert rows["nhis_health_in"]["effective"] == kc.STATUS_BLOCKED


def test_ingest_license_allowlist_includes_kogl0():
    assert kc.license_allows_ingest("kogl_type0")
    assert kc.license_allows_ingest("public_domain")
    assert kc.license_allows_ingest("datagokr_unrestricted")
    assert not kc.license_allows_ingest("kogl_type4")
    assert not kc.license_allows_ingest("cc_by_nc")
    assert not kc.license_allows_ingest(None)
