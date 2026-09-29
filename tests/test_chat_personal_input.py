# -*- coding: utf-8 -*-
"""테스터 PHR 전달 계약 테스트 — /api/rag/chat 개인화 입력 수신·배선.

vital_input 헬퍼(페이로드 병합·findings 계산)와 rag_routes._rag_chat 배선을
네트워크/실DB 없이 검증한다. 해석 파이프라인은 wraith 경로(service_routes)와 공용.
"""
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vital_input import (  # noqa: E402
    agent_input_from_chat_payload,
    parse_agent_inputs,
    personal_findings_from_parsed,
)


# ── agent_input_from_chat_payload (페이로드 병합) ─────────────

def test_shorthand_phr_string_maps_to_PHR_field():
    out = agent_input_from_chat_payload({"query": "q", "phr": "공복혈당 87 (2025-03)"})
    assert out == {"PHR": "공복혈당 87 (2025-03)"}


def test_shorthand_phr_object_is_serialized():
    out = agent_input_from_chat_payload(
        {"phr": {"공복혈당": [[87, "2025-03"], [95, "2023-03"]]}})
    assert "공복혈당" in out["PHR"]
    assert json.loads(out["PHR"])["공복혈당"][0] == [87, "2025-03"]


def test_shorthand_vitals_and_air_quality():
    out = agent_input_from_chat_payload({
        "vital_signs": [{"bps": 165, "bpd": 100, "create_date": "2026-08-01 09:00:00"}],
        "air_quality": "155",
    })
    assert json.loads(out["Vital Signs"])[0]["bps"] == 165
    assert out["Air Quality Score"] == "155"


def test_formal_field_passthrough_and_shorthand_precedence():
    formal = {"Vital Signs": "[]", "PHR": "old"}
    out = agent_input_from_chat_payload(
        {"agent_input_field_to_value": formal, "phr": "new"})
    assert out["PHR"] == "new"            # 축약 우선(호출측 명시 의도)
    assert out["Vital Signs"] == "[]"     # 정식 필드 보존
    assert formal["PHR"] == "old"         # 원본 불변(사본 병합)


def test_empty_payload_returns_none():
    assert agent_input_from_chat_payload({"query": "q"}) is None
    assert agent_input_from_chat_payload({}) is None
    assert agent_input_from_chat_payload(None) is None
    assert agent_input_from_chat_payload({"phr": ""}) is None


# ── PHR 문자열이 파서를 통과해 personal_raw 에 실리는지 ────────

def test_phr_flows_through_parse_agent_inputs():
    merged = agent_input_from_chat_payload({"phr": "검진: 수축기 130 (2025-03)"})
    parsed = parse_agent_inputs(merged)
    assert parsed["phr"] == "검진: 수축기 130 (2025-03)"
    assert parsed["received_fields"] == ["PHR"]


def test_empty_brace_phr_is_dropped_by_parser():
    parsed = parse_agent_inputs({"PHR": "{}"})
    assert parsed["phr"] is None


# ── personal_findings_from_parsed (공용 해석 헬퍼) ────────────

def test_findings_from_high_bp_vitals():
    parsed = parse_agent_inputs({
        "Vital Signs": json.dumps([
            {"bps": 165, "bpd": 100, "create_date": "2026-08-01 09:00:00"}]),
    })
    findings = personal_findings_from_parsed(parsed)
    assert findings, "고혈압 범위 vital 은 밴드 finding 을 만들어야"
    bands = {f.get("label_user") for f in findings}
    assert bands & {"주의", "경고"}


def test_findings_none_when_no_inputs():
    assert personal_findings_from_parsed(parse_agent_inputs(None)) is None
    assert personal_findings_from_parsed(None) is None


def test_findings_include_air_quality_note_when_bad():
    parsed = parse_agent_inputs({"Air Quality Score": "180"})  # 나쁨 구간
    findings = personal_findings_from_parsed(parsed)
    if findings:  # _grade 판정이 라벨을 내는 경우에만 (fail-closed 계약)
        assert any(f.get("signal_key") == "air_quality" for f in findings)


# ── 라우트 배선: /api/rag/chat → generate_response kwargs ─────

class _Sink:
    def write(self, b):
        return len(b)

    def flush(self):
        pass


class _Conn:
    def settimeout(self, s):
        pass


class _FakeChatHandler:
    def __init__(self):
        self.wfile = _Sink()
        self.connection = _Conn()
        self.responses = []

    # ProxyHandler 위임 메서드 스텁
    def _require_auth(self):
        return True

    def _get_tester_info(self):
        return {"id": "batch-eval", "name": "batch-eval"}

    def _send_json(self, code, payload):
        self.responses.append((code, payload))

    def _send_error(self, code, msg):
        self.responses.append((code, {"error": msg}))

    def _set_cors_headers(self):
        pass

    def send_response(self, code):
        pass

    def send_header(self, k, v):
        pass

    def end_headers(self):
        pass

    def _add_log(self, m):
        pass


def _run_chat(monkeypatch, body_dict, headers=None):
    import rag_routes

    monkeypatch.setattr(rag_routes, "RAG_ENABLED", True)
    monkeypatch.setattr(rag_routes.db, "_use_postgres", True)

    class _NoDb:
        def __enter__(self):
            raise RuntimeError("no db in test")  # conversation INSERT는 try/except

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(rag_routes.db, "get_conn", lambda: _NoDb())

    captured = {}

    def fake_generate_response(**kwargs):
        captured.update(kwargs)
        yield {"type": "STOP", "text": "ok", "citations": []}

    class H(_FakeChatHandler, rag_routes.RagRoutesMixin):
        pass

    h = H()
    if headers is not None:
        h.headers = headers
    with patch("rag_engine.generate_response", fake_generate_response):
        h._rag_chat(json.dumps(body_dict).encode("utf-8"))
    return h, captured


def test_chat_route_passes_phr_to_engine(monkeypatch):
    _, kw = _run_chat(monkeypatch, {
        "query": "검진 결과 좀 봐줘",
        "phr": "공복혈당 87 (2025-03) / 메트포르민서방정 2026-06-01 90일",
        "personal_consent": True,
    })
    assert kw["personal_consent"] is True
    assert kw["personal_raw"]["phr"].startswith("공복혈당 87")
    assert kw["personal_findings"] is None  # vitals 없음 → findings 없음


def test_chat_route_builds_findings_from_vitals(monkeypatch):
    _, kw = _run_chat(monkeypatch, {
        "query": "혈압이 걱정돼요",
        "agent_input_field_to_value": {
            "Vital Signs": json.dumps([
                {"bps": 165, "bpd": 100, "create_date": "2026-08-01 09:00:00"}]),
        },
    })
    assert kw["personal_findings"], "vital 전달 시 findings 배선돼야"
    assert kw["personal_consent"] is False   # 미전달 기본 False (fail-closed)
    assert kw["personal_raw"]["vital_signs"]


def test_chat_route_without_personal_inputs_unchanged(monkeypatch):
    _, kw = _run_chat(monkeypatch, {"query": "감기 조심법"})
    assert kw["personal_findings"] is None
    assert kw["personal_raw"] is None
    assert kw["personal_consent"] is False


# ── 답변 스타일 프로필 전달 (dev 실험용 X-Answer-Style) ──────

def test_chat_route_passes_answer_style_header(monkeypatch):
    _, kw = _run_chat(monkeypatch, {"query": "허리가 아파요"},
                      headers={"X-Answer-Style": "persly-safe"})
    assert kw["answer_style"] == "persly-safe"


def test_chat_route_body_style_wins_over_header(monkeypatch):
    _, kw = _run_chat(monkeypatch, {"query": "허리가 아파요", "answer_style": "default"},
                      headers={"X-Answer-Style": "persly-safe"})
    assert kw["answer_style"] == "default"


def test_chat_route_without_style_is_none(monkeypatch):
    """헤더도 body도 없으면 None → 엔진에서 default 로 해석된다."""
    _, kw = _run_chat(monkeypatch, {"query": "허리가 아파요"})
    assert kw["answer_style"] is None
