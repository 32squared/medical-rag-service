"""vital_rules.lookup_band 단위 테스트 — DB/네트워크/LLM 불필요.

검증: 결정적 밴드 라벨링(AND/OR 보수적 최댓값), fail-closed, 원시값 미반환(I1),
중립 라벨만(I12), 그리고 bands 추가가 KB 인용 본문을 바꾸지 않음(공존 불변식).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_reference_ranges import _RANGES, build_reference_documents, build_reference_rows
from vital_rules import lookup_band


def _bp(sys_v, dia_v):
    return {"systolic": sys_v, "diastolic": dia_v}


# ── 결정적 라벨링 (KR, KSH 2022 clinic) ──────────────────────────

def test_bp_kr_normal():
    r = lookup_band("blood_pressure", _bp(110, 70), locale="KR")
    assert r["match"] == "ok"
    assert r["label_user"] == "안정"


def test_bp_kr_elevated_and_category():
    # 수축기 120-129 그리고 이완기 <80 → 주의(주의혈압)
    r = lookup_band("blood_pressure", _bp(125, 70), locale="KR")
    assert r["label_user"] == "주의"


def test_bp_kr_prehtn_via_systolic_or():
    # 수축기 130-139 또는 이완기 80-89 → 주의(고혈압전단계)
    assert lookup_band("blood_pressure", _bp(135, 70), locale="KR")["label_user"] == "주의"
    # OR 분기: 수축기 정상이어도 이완기 80-89면 주의
    assert lookup_band("blood_pressure", _bp(118, 85), locale="KR")["label_user"] == "주의"


def test_bp_kr_stage1_warning():
    assert lookup_band("blood_pressure", _bp(145, 85), locale="KR")["label_user"] == "경고"
    # 이완기 단독 90-99로도 경고(1기) — OR
    assert lookup_band("blood_pressure", _bp(110, 95), locale="KR")["label_user"] == "경고"


def test_bp_kr_stage2_warning():
    assert lookup_band("blood_pressure", _bp(165, 80), locale="KR")["label_user"] == "경고"
    assert lookup_band("blood_pressure", _bp(120, 105), locale="KR")["label_user"] == "경고"


def test_bp_conservative_max_on_overlap():
    # 수축기 165(2기) + 이완기 85(전단계) → 가장 보수적 경고 채택
    r = lookup_band("blood_pressure", _bp(165, 85), locale="KR")
    assert r["label_user"] == "경고"


# ── US 로케일 (ACC/AHA 2017) ─────────────────────────────────────

def test_bp_us_stage1_at_130():
    # US Stage1 = 수축기 130-139 → 주의
    assert lookup_band("blood_pressure", _bp(135, 70), locale="US")["label_user"] == "주의"


def test_bp_us_stage2_at_140():
    # US Stage2 = 수축기 140 이상 → 경고 (KR은 같은 값이 1기)
    assert lookup_band("blood_pressure", _bp(145, 80), locale="US")["label_user"] == "경고"


# ── fail-closed ──────────────────────────────────────────────────

def test_unknown_signal_fail_closed():
    r = lookup_band("unknown_signal", 123, locale="KR")
    assert r["match"] == "no_match"
    assert r["label_user"] is None


def test_home_context_not_structured_fail_closed():
    # 가정혈압(home)은 아직 bands 미구조화 → no_match (라벨 강제 생성 안 함)
    r = lookup_band("blood_pressure", _bp(140, 90), context="home", locale="KR")
    assert r["match"] == "no_match"
    assert r["label_user"] is None


def test_missing_axis_fail_closed():
    # 다축 신호인데 한 축 결손 → 안전하게 처리(라벨 강제 생성 금지)
    r = lookup_band("blood_pressure", {"systolic": 110}, locale="KR")
    # 이완기 결손 → 정상혈압(and) 불성립. 어떤 카테고리도 확정 매칭 안 됨.
    assert r["label_user"] is None or r["match"] == "no_match"


# ── 원시값 미반환 (I1) + 중립 라벨만 (I12) ──────────────────────

def test_no_raw_value_in_result():
    r = lookup_band("blood_pressure", _bp(165, 105), locale="KR")
    # 결과 직렬화 어디에도 입력 원시값·임상 역치가 노출되지 않아야 함
    blob = json.dumps(r, ensure_ascii=False)
    for raw in ("165", "105", "160", "100", "min", "max"):
        assert raw not in blob, f"원시값/역치 '{raw}' 누출"


def test_label_user_is_neutral_only():
    for sys_v, dia_v in [(110, 70), (125, 70), (135, 85), (165, 105)]:
        lu = lookup_band("blood_pressure", _bp(sys_v, dia_v), locale="KR")["label_user"]
        assert lu in ("안정", "주의", "경고")


def test_clinical_label_internal_not_user_label():
    # clinical_label(예 "고혈압 2기")은 내부 동봉되나 label_user와 구별 — 표면화는 label_user만
    r = lookup_band("blood_pressure", _bp(165, 105), locale="KR")
    assert r["clinical_label"] == "고혈압 2기"
    assert r["label_user"] == "경고"
    assert r["clinical_label"] != r["label_user"]


# ── 공존 불변식: bands 추가가 기존 자산을 깨지 않음 ──────────────

def test_kb_documents_unchanged_by_bands():
    """build_reference_documents는 rule만 읽으므로 KB 본문에 bands 흔적 없음."""
    for doc in build_reference_documents():
        md = doc["content_md"]
        for leak in ("label_user", "systolic", "diastolic", "combine", "bands"):
            assert leak not in md, f"{doc['title']}: KB 본문에 '{leak}' 누출"


def test_ranges_json_still_has_label_and_rule():
    """기존 계약(test_reference_ranges) 불변: 모든 구간에 label·rule 유지."""
    for row in build_reference_rows():
        for rng in json.loads(row["ranges_json"]):
            assert rng.get("label") and rng.get("rule")


def test_every_band_has_valid_axis_and_bounds():
    """구조화 무결성: 모든 band가 유효 axis + 수치 경계."""
    for r in _RANGES:
        for rng in r.get("ranges", []):
            for band in rng.get("bands", []):
                assert band.get("axis") in ("systolic", "diastolic", "value")
                assert ("min" in band) or ("max" in band)
