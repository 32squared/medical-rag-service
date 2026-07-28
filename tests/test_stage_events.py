# -*- coding: utf-8 -*-
"""파이프라인 단계 이벤트 테스트 — 파트너 앱 '생각 중→검색 중→답변 중' 표시 계약.

engine: generate_response 스트림에 stage INFO(searching→answering)가 올바른 순서로.
adapter: stage INFO → wraith PROGRESS(strid=stage_*) 변환, 구 프론트 무해성.
"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_generate_response import (  # noqa: E402
    _make_chunk,
    _make_provider_mock,
    _run_generate_response,
)
import wraith_sse_adapter as wa  # noqa: E402


def _stage_indices(events):
    """이벤트 리스트에서 (stage명 → index) 매핑."""
    out = {}
    for i, ev in enumerate(events):
        if ev.get("type") == "INFO" and (ev.get("data") or {}).get("status") == "stage":
            out[ev["data"].get("stage")] = i
    return out


# ── engine ──────────────────────────────────────────────────

def test_normal_path_emits_searching_then_answering():
    events = _run_generate_response()
    stages = _stage_indices(events)
    assert "searching" in stages and "answering" in stages
    assert stages["searching"] < stages["answering"]

    # searching 은 search_results INFO 이전
    sr_idx = next(i for i, e in enumerate(events)
                  if e.get("type") == "INFO" and "search_results" in (e.get("data") or {}))
    assert stages["searching"] < sr_idx

    # answering 은 첫 GENERATION 이전
    gen_idx = next(i for i, e in enumerate(events) if e.get("type") == "GENERATION")
    assert stages["answering"] < gen_idx


def test_stage_events_do_not_alter_stop_contract():
    events = _run_generate_response()
    stop = [e for e in events if e.get("type") == "STOP"]
    assert len(stop) == 1
    assert "citations" in stop[0]


def test_emergency_redirect_path_has_no_stage_events():
    # EMERGENCY_REDIRECTED 상태의 즉시응답 경로는 검색·LLM 모두 미실행 →
    # stage 이벤트 0 (즉시 GENERATION+STOP)
    events = _run_generate_response(
        mock_conv_state={"emergency_state": "EMERGENCY_REDIRECTED"})
    stages = _stage_indices(events)
    assert stages == {}
    assert any(e.get("type") == "STOP" for e in events)


# ── adapter ─────────────────────────────────────────────────

def test_adapter_maps_stage_to_progress():
    out = wa.adapt_event(
        {"type": "INFO", "data": {"status": "stage", "stage": "searching"}})
    assert len(out) == 1
    ev = out[0]
    assert ev["type"] == "PROGRESS"
    assert ev["strid"] == "stage_searching"
    assert ev["status"] == "IN_PROGRESS"
    assert ev["display_message"] == "근거 자료를 검색하고 있어요"
    assert ev["metadata"]["label"] == "searching"


def test_adapter_maps_answering_stage():
    out = wa.adapt_event(
        {"type": "INFO", "data": {"status": "stage", "stage": "answering"}})
    assert out[0]["strid"] == "stage_answering"
    assert out[0]["display_message"] == "답변을 작성하고 있어요"


def test_adapter_unknown_stage_falls_back_to_raw_name():
    out = wa.adapt_event(
        {"type": "INFO", "data": {"status": "stage", "stage": "future_stage"}})
    assert out[0]["type"] == "PROGRESS"
    assert out[0]["strid"] == "stage_future_stage"
    assert out[0]["display_message"] == "future_stage"


def test_adapter_started_mapping_unchanged():
    out = wa.adapt_event({"type": "INFO", "data": {"status": "started"}})
    assert out[0]["type"] == "PROGRESS"
    assert out[0]["strid"] == "pipeline_start"
