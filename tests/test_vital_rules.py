"""vital_rules.lookup_band 단위 테스트 — DB/네트워크/LLM 불필요.

검증: 결정적 밴드 라벨링(AND/OR 보수적 최댓값), fail-closed, 원시값 미반환(I1),
중립 라벨만(I12), 그리고 bands 추가가 KB 인용 본문을 바꾸지 않음(공존 불변식).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed_reference_ranges import _RANGES, build_reference_documents, build_reference_rows
from vital_rules import DENY_SIGNALS, lookup_band, run


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


def test_bp_home_context_above_threshold_warning():
    # 가정혈압 135/85 이상 → 경고 (진료실 기준과 다름)
    assert lookup_band("blood_pressure", _bp(140, 90), context="home", locale="KR")["label_user"] == "경고"
    assert lookup_band("blood_pressure", _bp(136, 80), context="home", locale="KR")["label_user"] == "경고"


def test_bp_home_context_below_threshold_fail_closed():
    # 시드는 home 정상 tier를 정의하지 않음 → 거짓안심 비대칭상 no_match(안심 라벨 강제 안 함)
    r = lookup_band("blood_pressure", _bp(110, 70), context="home", locale="KR")
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


# ── 단축 신호 (혈당·당화혈색소·SpO2·체온·BMI·심박) ──────────────

def test_fasting_glucose_tiers():
    assert lookup_band("fasting_glucose", 90, locale="KR")["label_user"] == "안정"
    assert lookup_band("fasting_glucose", 110, locale="KR")["label_user"] == "주의"
    assert lookup_band("fasting_glucose", 140, locale="KR")["label_user"] == "경고"


def test_hba1c_tiers():
    assert lookup_band("hba1c", 5.4, locale="KR")["label_user"] == "안정"
    assert lookup_band("hba1c", 6.0, locale="KR")["label_user"] == "주의"
    assert lookup_band("hba1c", 7.0, locale="KR")["label_user"] == "경고"


def test_spo2_tiers_global_all_fallback():
    # spo2는 locale=GLOBAL·population=all — KR/adult 요청도 폴백 선택돼야 함
    assert lookup_band("spo2", 98)["label_user"] == "안정"
    assert lookup_band("spo2", 92)["label_user"] == "주의"
    assert lookup_band("spo2", 88)["label_user"] == "경고"


def test_bmi_tiers():
    assert lookup_band("bmi", 17, locale="KR")["label_user"] == "주의"   # 저체중
    assert lookup_band("bmi", 21, locale="KR")["label_user"] == "안정"
    assert lookup_band("bmi", 27, locale="KR")["label_user"] == "주의"   # 1단계
    assert lookup_band("bmi", 32, locale="KR")["label_user"] == "경고"   # 2단계


def test_body_temperature_adult_tiers():
    assert lookup_band("body_temperature", 36.6, population="adult")["label_user"] == "안정"
    assert lookup_band("body_temperature", 37.5, population="adult")["label_user"] == "주의"
    assert lookup_band("body_temperature", 38.5, population="adult")["label_user"] == "경고"


def test_heart_rate_single_normal_band():
    assert lookup_band("heart_rate", 72)["label_user"] == "안정"
    # 범위 밖은 tier 미시드 → no_match(fail-closed)
    assert lookup_band("heart_rate", 150)["match"] == "no_match"


def test_pediatric_temp_not_structured_fail_closed():
    # 소아 발열은 고위험·미구조화 → no_match(라벨 강제 생성 금지)
    assert lookup_band("body_temperature", 38.5, population="child")["match"] == "no_match"


# ── I8 device_grade deny ────────────────────────────────────────

def test_wellness_grade_denied():
    # 워치(웰니스 등급) SpO2는 임상밴드 비활성 → denied
    r = lookup_band("spo2", 92, device_grade="wellness")
    assert r["match"] == "denied"
    assert r["label_user"] is None


def test_deny_signal_list():
    for sig in DENY_SIGNALS:
        r = lookup_band(sig, 1)
        assert r["match"] == "denied"
        assert r["label_user"] is None


# ── I12 핵심: 질환명 임상 라벨이 사용자 라벨로 새지 않음 ──────────

def test_disease_clinical_labels_never_become_user_label():
    """시드의 질환명 라벨(당뇨병 기준/N단계 비만 등)은 clinical_label 내부에만,
    사용자 label_user는 항상 중립 3단 — 개인귀속 진단 0(I12/I2)."""
    cases = [
        ("fasting_glucose", 140, "당뇨병 기준"),
        ("hba1c", 7.0, "당뇨병 기준"),
        ("bmi", 32, "2단계 비만"),
        ("blood_pressure", _bp(165, 105), "고혈압 2기"),
    ]
    disease_words = ("당뇨", "비만", "고혈압", "저산소", "병")
    for signal, value, expected_clinical in cases:
        r = lookup_band(signal, value, locale="KR")
        assert r["clinical_label"] == expected_clinical          # 내부엔 임상 라벨
        assert r["label_user"] in ("안정", "주의", "경고")        # 사용자엔 중립만
        for w in disease_words:
            assert w not in (r["label_user"] or "")              # 질환명 누출 0


# ── C15 run(): vital_input 레코드 → findings 브리지 ──────────────

def _vital_record(**kw):
    """vital_input.parse_vital_signs 출력 형태 모사."""
    return kw


def test_run_full_record_produces_findings():
    rec = _vital_record(bps=165, bpd=105, bpm=72, spo2=98, fever=36.6, stress=50)
    findings = run(rec)
    signals = {f["signal_key"]: f["label_user"] for f in findings}
    assert signals["blood_pressure"] == "경고"
    assert signals["heart_rate"] == "안정"
    assert signals["spo2"] == "안정"
    assert signals["body_temperature"] == "안정"
    # stress는 공인 밴드 없음 → finding 없음
    assert "stress" not in signals


def test_run_blood_pressure_requires_both_axes():
    # 이완기 결손 → 혈압 finding 미생성
    findings = run(_vital_record(bps=140, bpm=80))
    assert not any(f["signal_key"] == "blood_pressure" for f in findings)
    assert any(f["signal_key"] == "heart_rate" for f in findings)


def test_run_wellness_grade_yields_no_findings():
    # 워치(웰니스)면 임상밴드 전부 denied → findings 0 (워치는 wellness_rules 별도 경로)
    rec = _vital_record(bps=165, bpd=105, spo2=92)
    assert run(rec, device_grade="wellness") == []


def test_run_skips_no_match_signals():
    # 범위 밖 심박(서맥/빈맥 미시드) → no_match → finding 없음(fail-closed)
    findings = run(_vital_record(bpm=150))
    assert not any(f["signal_key"] == "heart_rate" for f in findings)


def test_run_findings_carry_no_raw_value():
    findings = run(_vital_record(bps=165, bpd=105, fever=38.5))
    blob = json.dumps(findings, ensure_ascii=False)
    for raw in ("165", "105", "38.5", "min", "max"):
        assert raw not in blob, f"finding에 원시값/역치 '{raw}' 누출"


def test_run_findings_have_citation_alias():
    # 각 finding은 인용 동반적재용 cite_doc_id를 갖는다(C19/11 §5 배선 전제)
    for f in run(_vital_record(bps=145, bpd=92)):
        assert f["cite_doc_id"]
        assert f["label_user"] in ("안정", "주의", "경고")


def test_run_empty_or_invalid_record():
    assert run({}) == []
    assert run(None) == []
