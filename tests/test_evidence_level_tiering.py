"""
출처 티어 기반 evidence_level 매핑 테스트 (04-kb-expansion-list.md §2).

자동 수집기의 'B 일괄' 문제를 출처 기반 차등(A/B/C)으로 교체한 것을 검증.
"""

from retrieval_router import evidence_level_for_source


def test_domestic_public_sources_are_A():
    """국내 공공 권위 출처(KDCA/MFDS/NEMC/법령)는 A."""
    for sid in ["kdca_api", "health_kdca", "mfds", "mfds_dur", "nemc", "kr_law", "nip"]:
        assert evidence_level_for_source(sid) == "A", sid


def test_b_tier_boundary_via_rank(monkeypatch):
    """rank 3~4 출처는 B (경계 로직 검증).

    현재 ROUTE_TO_KB_SOURCE에 rank 3~4(WHO/CDC/DailyMed) source_id가 매핑돼
    있지 않아 실데이터로는 B가 안 나온다(해당 출처 적재 시 매핑 추가하면 활성).
    여기서는 priority_rank→level 경계 로직만 검증한다.
    """
    import retrieval_router as rr
    monkeypatch.setattr(rr, "source_priority_for", lambda sid: 3)
    assert rr.evidence_level_for_source("anything") == "B"
    monkeypatch.setattr(rr, "source_priority_for", lambda sid: 4)
    assert rr.evidence_level_for_source("anything") == "B"


def test_papers_and_unmapped_are_C():
    """논문(PubMed/PMC)·미매핑 글로벌·미상 출처는 현재 C."""
    for sid in ["pubmed", "pmc_oa", "who", "cdc", "nice", "___unknown___"]:
        assert evidence_level_for_source(sid) == "C", sid


def test_collector_sources_become_A_not_B():
    """자동 수집기 출처 5종이 모두 A로 라벨(기존 'B 일괄' 교체 확인)."""
    for sid in ["mfds", "nemc", "kdca_api", "health_kdca", "mfds_drug_info"]:
        assert evidence_level_for_source(sid) == "A", sid
