"""
비식별 개인 맥락 LLM 주입(방향 2) 게이트 검증 — personal_llm_context.

플래그·동의·국외이전·응급·관련성·라벨온리(G1~G6)가 fail-closed로 작동하고,
주입 문자열에 원시값·진단명이 없는지(라벨만) 확인한다. 정본: docs/plan/17.
"""

import os
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as vr  # noqa: E402
import personal_llm_context as plc  # noqa: E402
from personalization_safety import scan_personal_block  # noqa: E402

DOMESTIC = SimpleNamespace(provider="self_hosted", provider_id="kr1", model_id="m")
FOREIGN = SimpleNamespace(provider="openai", provider_id="gpt", model_id="gpt-5")
Q = "혈압 낮추려면 뭘 해야 하나요?"


def _findings():
    return vr.run({"bps": 152, "bpd": 96})   # 혈압 경고


def _on(monkeypatch):
    monkeypatch.setenv("PERSONAL_SIGNAL_TO_LLM", "true")


# ── G1 기능 플래그 ───────────────────────────────────────────
def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PERSONAL_SIGNAL_TO_LLM", raising=False)
    assert plc.build_llm_context(_findings(), Q, consent=True, provider=DOMESTIC) == ""


# ── G2 동의 ──────────────────────────────────────────────────
def test_no_consent_no_inject(monkeypatch):
    _on(monkeypatch)
    assert plc.build_llm_context(_findings(), Q, consent=False, provider=DOMESTIC) == ""


# ── G3 응급 ──────────────────────────────────────────────────
def test_emergency_suppressed(monkeypatch):
    _on(monkeypatch)
    assert plc.build_llm_context(_findings(), Q, consent=True, provider=DOMESTIC,
                                 is_emergency=True) == ""


# ── G4 국외이전 ──────────────────────────────────────────────
def test_domestic_provider_ok(monkeypatch):
    _on(monkeypatch)
    out = plc.build_llm_context(_findings(), Q, consent=True, provider=DOMESTIC)
    assert out and "혈압=경고" in out


def test_foreign_provider_blocked_without_ack(monkeypatch):
    _on(monkeypatch)
    monkeypatch.delenv("ALLOW_CROSS_BORDER_PERSONAL", raising=False)
    assert plc.build_llm_context(_findings(), Q, consent=True, provider=FOREIGN) == ""


def test_foreign_provider_allowed_with_ack(monkeypatch):
    _on(monkeypatch)
    monkeypatch.setenv("ALLOW_CROSS_BORDER_PERSONAL", "true")
    out = plc.build_llm_context(_findings(), Q, consent=True, provider=FOREIGN)
    assert out and "혈압=경고" in out


# ── G5 관련성 ────────────────────────────────────────────────
def test_unrelated_query_no_inject(monkeypatch):
    _on(monkeypatch)
    assert plc.build_llm_context(_findings(), "감기약 먹어도 되나요?",
                                 consent=True, provider=DOMESTIC) == ""


# ── G6 라벨-온리(원시값/진단명 0) ────────────────────────────
def test_label_only_no_raw_or_diagnosis(monkeypatch):
    _on(monkeypatch)
    out = plc.build_llm_context(_findings(), Q, consent=True, provider=DOMESTIC)
    assert not re.search(r"\d{2,}", out)          # 원시값(2자리+) 없음
    assert "고혈압" not in out                      # 진단명 없음
    assert scan_personal_block(out)["safe"]        # 백스톱 통과


# ── 미리보기(게이트 무관, 내용만) ────────────────────────────
def test_preview_independent_of_flags():
    # 플래그 off여도 preview는 '주입될 내용'을 보여준다(UI용)
    out = plc.preview_context(_findings(), Q)
    assert "혈압=경고" in out
    assert plc.preview_context(_findings(), "감기약 먹어도 되나요?") == ""
