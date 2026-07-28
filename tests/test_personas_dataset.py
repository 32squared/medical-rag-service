"""
페르소나 데이터셋 + 개인화 미리보기 검증.

test_personas/personas.json이 계약(agent_input_field_to_value)에 맞고,
persona_test_server.compute_preview가 각 페르소나에 대해 결정적 findings/safe_block을
오류 없이 만들어내는지(원시값 미노출) 확인한다. 백엔드/DB/LLM 불필요.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import persona_test_server as pts  # noqa: E402


def _all():
    return pts.load_personas()["personas"]


def test_dataset_schema():
    personas = _all()
    assert len(personas) >= 20, "페르소나 최소 20개 요건"
    ids = [p["id"] for p in personas]
    assert len(ids) == len(set(ids)), "persona id 중복"
    for p in personas:
        assert p.get("name") and p.get("sample_queries"), p["id"]
        assert isinstance(p.get("vitals"), list)


def test_every_persona_has_personalization_data():
    """각 페르소나에 상황에 맞는 개인화 데이터가 채워져 있어야 한다."""
    for p in _all():
        # vitals에 측정 신호가 1개 이상
        vit = p.get("vitals") or []
        assert vit, f"{p['id']}: vitals 비어있음"
        signal_keys = {k for r in vit for k in r if k != "create_date"}
        assert signal_keys, f"{p['id']}: 측정 신호 없음"
        # 환경·PHR 필드 존재(빈 값이라도 키는 채움)
        assert "air_quality" in p and "phr" in p, p["id"]
        assert p.get("expected_label"), f"{p['id']}: expected_label 누락"


def test_agent_input_roundtrips():
    from vital_input import parse_agent_inputs
    p = next(x for x in _all() if x["id"] == "healthy_office")
    ai = pts.build_agent_input(p)
    parsed = parse_agent_inputs(ai)
    assert parsed["vital_signs"], "Vital Signs 파싱 실패"
    assert parsed["vital_signs"][-1].get("bps") == 118


def test_preview_runs_for_every_persona():
    produced = 0
    for p in _all():
        out = pts.compute_preview(p, (p.get("sample_queries") or [""])[0])
        assert set(out) >= {"findings", "safe_block", "summary", "agent_input"}
        assert isinstance(out["safe_block"], str)
        for f in out["findings"]:
            assert f["label_user"] in ("안정", "주의", "경고", None)
            # 원시값 미노출 — findings에 측정 숫자 키가 없어야 함
            assert "value" not in f and "systolic" not in f
        if out["findings"]:
            produced += 1
    assert produced >= 6, "밴드 findings를 내는 페르소나가 너무 적음"


def test_known_persona_labels():
    by = {p["id"]: p for p in _all()}
    # 고혈압 어르신 → 혈압 경고
    hs = pts.compute_preview(by["hypertension_senior"], "혈압이 높게 나왔어요")
    bp = [f for f in hs["findings"] if f["signal"] == "blood_pressure"]
    assert bp and bp[0]["label_user"] == "경고"
    # 건강한 직장인 → 혈압 안정
    ho = pts.compute_preview(by["healthy_office"], "두통이 있어요")
    bp2 = [f for f in ho["findings"] if f["signal"] == "blood_pressure"]
    assert bp2 and bp2[0]["label_user"] == "안정"
    # 소아 보호자 → 성인 밴드 미적용(개인화 생략)
    ped = pts.compute_preview(by["pediatric_guardian"], "아이가 열이 나요")
    assert ped["findings"] == []
