"""
claim↔근거 의미일치(어휘 겹침) 검증 테스트 (07-revised-plan.md §9.1).

인용된 문장이 인용 근거 청크와 실제로 겹치는지(결정적 근거일치 근사) 검증.
"""

from citation_verifier import check_citation_grounding


def test_grounded_claim_passes():
    """인용 근거에 claim 내용어가 충분히 등장하면 grounded."""
    answer = "발열은 감염의 흔한 증상이며 38도 이상이면 주의가 필요합니다 [E1]."
    evidence = {"E1": "발열은 감염 등으로 체온이 38도 이상 오르는 증상입니다. 감염이 흔한 원인입니다."}
    r = check_citation_grounding(answer, evidence)
    assert r["checked"] == 1
    assert r["grounded"] == 1
    assert r["grounded_ratio"] == 1.0
    assert r["weak_claims"] == []


def test_ungrounded_claim_flagged():
    """인용 근거와 전혀 무관한 내용을 인용하면 weak_grounding으로 표시."""
    answer = "혈압약은 매일 같은 시간에 복용하는 것이 중요합니다 [E1]."
    evidence = {"E1": "독감 예방접종은 매년 가을에 맞는 것이 권장됩니다."}
    r = check_citation_grounding(answer, evidence)
    assert r["checked"] == 1
    assert r["grounded"] == 0
    assert r["grounded_ratio"] < 1.0
    assert len(r["weak_claims"]) == 1


def test_numeric_marker_key_supported():
    """[1] 형식 마커도 매핑된다."""
    answer = "기침은 호흡기 감염에서 자주 나타납니다 [1]."
    evidence = {"1": "기침은 호흡기 감염의 흔한 증상으로 나타납니다."}
    r = check_citation_grounding(answer, evidence)
    assert r["grounded"] == 1


def test_no_citation_skips():
    r = check_citation_grounding("증상이 있으면 상담하세요.", {"E1": "..."})
    assert r["checked"] == 0
    assert r["grounded_ratio"] == 1.0


def test_empty_inputs_skip():
    assert check_citation_grounding("", {"E1": "x"})["notes"] == "skip"
    assert check_citation_grounding("발열 [E1].", {})["notes"] == "skip"


def test_mixed_grounded_and_weak():
    answer = ("발열은 감염의 증상입니다 [E1]. 혈압약은 식후에 복용합니다 [E2].")
    evidence = {
        "E1": "발열은 감염으로 인한 증상입니다.",
        "E2": "예방접종 일정은 보건소에서 확인할 수 있습니다.",  # 무관
    }
    r = check_citation_grounding(answer, evidence)
    assert r["checked"] == 2
    assert r["grounded"] == 1
    assert len(r["weak_claims"]) == 1
