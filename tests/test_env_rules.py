"""
환경(공기질) 비해석적 노트 — env_rules + personal_context 결합 (5층 환경×건강).

air_quality_finding 매핑(fail-closed)과, personal_context가 환경 finding을
호흡기 scope 질의에서만 '환기 권유' 노트로 결합하는지(과노출 차단·진단 아님)를 검증한다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import env_rules as er  # noqa: E402
import personal_context as pc  # noqa: E402


# ── 단위: 등급 매핑 ──────────────────────────────────────────
def test_label_mapping():
    assert er.air_quality_finding("나쁨")["label_user"] == "주의"
    assert er.air_quality_finding("매우나쁨")["label_user"] == "경고"
    assert er.air_quality_finding("보통") is None
    assert er.air_quality_finding("좋음") is None
    assert er.air_quality_finding("") is None
    assert er.air_quality_finding(None) is None


def test_numeric_cai_mapping():
    assert er.air_quality_finding("300")["label_user"] == "경고"   # 매우나쁨
    assert er.air_quality_finding(150)["label_user"] == "주의"     # 나쁨
    assert er.air_quality_finding(45) is None                      # 좋음


def test_finding_shape_non_causal():
    f = er.air_quality_finding("나쁨")
    assert f["signal_key"] == "air_quality" and f["kind"] == "environment"
    assert f["clinical_label"] is None and f["match"] == "ok"
    # 비인과적·환기 권유 — 원인 단정 문구 없음
    assert "환기" in f["sentence"]
    assert "때문에" not in f["sentence"] and "원인입니다" not in f["sentence"]


# ── 결합: personal_context 관련성 게이트 ─────────────────────
def test_surfaces_on_respiratory_query():
    f = er.air_quality_finding("매우나쁨")
    blk = pc.safe_block([f], "기침이 오래가고 가래가 많아요")
    assert blk and "실내 공기질" in blk and "환기" in blk


def test_suppressed_on_unrelated_query():
    f = er.air_quality_finding("나쁨")
    # 혈압 질의엔 환경 노트 미표면화(과노출 차단)
    assert pc.safe_block([f], "혈압이 높게 나왔어요") == ""


def test_combined_with_vital_finding():
    import vital_rules as vr
    findings = vr.run({"spo2": 91}) + [er.air_quality_finding("나쁨")]
    blk = pc.safe_block(findings, "기침이 나고 숨쉬기 답답해요")
    assert "산소포화도" in blk and "실내 공기질" in blk


# ── 페르소나 미리보기 통합 ───────────────────────────────────
def test_persona_preview_includes_env():
    import persona_test_server as pts
    data = pts.load_personas()
    copd = next(p for p in data["personas"] if p["id"] == "copd_history")  # air_quality 매우나쁨
    out = pts.compute_preview(copd, "기침이 안 멎어요")
    sigs = {f["signal"] for f in out["findings"]}
    assert "air_quality" in sigs
    assert "실내 공기질" in out["safe_block"]
    # 공기질 보통 페르소나는 환경 노트 없음
    healthy = next(p for p in data["personas"] if p["id"] == "healthy_office")
    out2 = pts.compute_preview(healthy, "기침이 나요")
    assert "air_quality" not in {f["signal"] for f in out2["findings"]}
