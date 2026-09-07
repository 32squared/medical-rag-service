# -*- coding: utf-8 -*-
"""개인 데이터 예외가 시스템 프롬프트 '안'에 심기는지 고정.

배경(실측): PHR을 프롬프트 뒤에 덧붙이기만 하면 상단 "오직 검토 자료만 사용"
프레이밍과 절대 원칙 2(컨텍스트 외 정보 금지)에 눌려 답변 활용률이 0/10이었다.
예외를 원칙 안으로 옮긴 뒤 5/10로 올랐고 안전 판정은 10/10을 유지했다.
이 테스트는 그 구조(프레이밍 교체 + 원칙2 내 예외)가 되돌아가지 않게 잠근다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import _build_rag_system_prompt  # noqa: E402


def _p(kind):
    return _build_rag_system_prompt("q", [], gate_result=None, personal_kind=kind)


# ── 기본(개인 데이터 없음) — 기존 계약 불변 ──────────────────

def test_default_keeps_context_only_framing():
    p = _p("")
    assert "오직 아래 ## 검토 자료에 명시된 사실만 사용" in p
    assert "개인 데이터 예외" not in p


def test_default_signature_backward_compatible():
    # personal_kind 미전달 호출(기존 코드 경로)이 그대로 동작해야
    assert _build_rag_system_prompt("q", []) == _p("")


# ── raw(전체 PHR) ────────────────────────────────────────────

def test_raw_relaxes_framing_and_rule2():
    p = _p("raw")
    assert "오직 아래 ## 검토 자료에 명시된 사실만 사용" not in p
    assert "[사용자 개인 건강 데이터]에 명시된 사실만 사용" in p
    assert "개인 데이터 예외" in p
    # 예외는 원칙 2 '안'에 있어야 한다 — 뒤에 덧붙이면 무력했다
    i2 = p.index("2. [컨텍스트 외 정보 금지]")
    i3 = p.index("3. [근거 충돌 시 보수성]")
    assert i2 < p.index("[개인 데이터 예외]") < i3


def test_raw_requires_attribution_and_marker():
    p = _p("raw")
    assert "알려주신 기록의" in p          # (a) 출처 명시 의무
    assert "[내 기록]" in p                # (b) 전용 마커
    assert "되묻지 마시오" in p            # 이미 받은 정보 재질문 금지


def test_raw_keeps_diagnosis_and_dose_ban():
    p = _p("raw")
    # (c) 예외가 진단·용량조정·처방 금지를 풀어주지 않아야 한다
    assert "확정 진단·용량 조정·처방을 하지 말고" in p
    assert "[진단 단정 금지]" in p
    assert "[처방·검사 지시 금지]" in p


# ── band(밴드 라벨만) ────────────────────────────────────────

def test_band_allows_label_but_not_raw_values():
    p = _p("band")
    assert "[비식별 개인 맥락](구간 라벨)" in p
    assert "원시 수치·진단명을 추측해 만들어내지 말고" in p
    assert "[내 기록]" not in p   # 마커는 raw 전용


def test_band_and_raw_differ():
    assert _p("band") != _p("raw")


# ── 마커가 인용 검증과 충돌하지 않는지 ───────────────────────

def test_my_record_marker_not_matched_by_citation_regex():
    from rag_engine import _CITATION_PATTERN
    assert _CITATION_PATTERN.findall("혈압 130/89 [내 기록][2]") == ["2"]
    assert _CITATION_PATTERN.findall("[내 기록]") == []
