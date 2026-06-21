"""wraith Run Graph 호환 계층 단위 테스트 — DB/네트워크 불필요.

대상: wraith_sse_adapter(이벤트 변환), auth_resolver(이중 인증), vital_input(개인화 파싱).
계약 기준: docs/api/COMPAT-run-graph.md.
"""

import base64
import hashlib
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wraith_sse_adapter import (
    adapt_event,
    chunk_to_search_result,
    new_usage_strid,
    start_event,
)
from auth_resolver import decode_bearer, resolve_user
from vital_input import parse_agent_inputs, parse_vital_signs, summarize_for_audit


# ─────────────────────── SSE 어댑터 ───────────────────────

def test_start_event_shape():
    ev = start_event("conv-123")
    assert ev["type"] == "INFO"
    assert ev["data"]["conversation_strid"] == "conv-123"
    assert ev["data"]["graph_usage_strid"].startswith("conv-123_")


def test_usage_strid_format():
    s = new_usage_strid("abc")
    assert s.startswith("abc_") and len(s) > 10


def test_generation_passthrough():
    out = adapt_event({"type": "GENERATION", "text": "안녕"})
    assert out == [{"type": "GENERATION", "text": "안녕"}]


def test_keepalive_passthrough():
    assert adapt_event({"type": "KEEP_ALIVE"}) == [{"type": "KEEP_ALIVE"}]


def test_search_results_mapped_to_wraith_shape():
    ours = {"type": "INFO", "data": {"search_results": [{
        "chunk_id": "c1", "document_id": "d1",
        "content": "발열은 38.0℃ 이상…", "source_id": "health_kdca",
        "title": "발열", "source_url": "https://health.kdca.go.kr/x",
        "evidence_level": "A", "score": 0.9,
    }]}}
    out = adapt_event(ours)
    assert len(out) == 1
    sr = out[0]["data"]["search_results"][0]
    # 원본 SearchResult 필수 필드 (WEBPAGE 형태)
    assert sr["strid"] == "c1"
    assert sr["content_type"] == "WEBPAGE"
    assert sr["source_type"] == "WEB"
    assert sr["url"] == "https://health.kdca.go.kr/x"
    assert sr["source"] == "질병관리청 국가건강정보포털"
    assert sr["relevant_chunks"][0]["chunk_text"].startswith("발열은")
    assert sr["relevant_chunks"][0]["start_offset"] == -1
    assert sr["display_link"] == "health.kdca.go.kr"


def test_started_info_becomes_progress():
    out = adapt_event({"type": "INFO", "data": {"status": "started", "query": "x"}})
    assert out[0]["type"] == "PROGRESS"
    assert out[0]["status"] == "IN_PROGRESS"


def test_evidence_check_wrapped_as_progress():
    out = adapt_event({"type": "EVIDENCE_CHECK", "data": {
        "quality": "high", "decision": "PASS", "relevant_count": 4}})
    assert out[0]["type"] == "PROGRESS"
    assert out[0]["metadata"]["label"] == "evidence_check"
    assert out[0]["metadata"]["quality"] == "high"


def test_stop_splits_into_token_usage_and_bare_stop():
    out = adapt_event({"type": "STOP", "text": "답변", "citations": [],
                       "tokens": {"input": 100, "output": 20}})
    assert out[0]["type"] == "INFO"
    usage = list(out[0]["data"]["token_usage"].values())[0]
    assert usage == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    # 원본 STOP은 빈 종료 신호
    assert out[-1] == {"type": "STOP"}


def test_stop_without_tokens_is_bare():
    out = adapt_event({"type": "STOP", "text": "x"})
    assert out == [{"type": "STOP"}]


def test_error_followed_by_stop():
    out = adapt_event({"type": "ERROR", "message": "boom"})
    assert out[0]["type"] == "ERROR" and out[0]["message"] == "boom"
    assert out[1] == {"type": "STOP"}  # 원본 규약: ERROR 뒤 STOP


def test_chunk_without_url():
    sr = chunk_to_search_result({"chunk_id": "c2", "content": "내용", "source_id": "unknown_src"})
    assert sr["url"] == "" and sr["display_link"] == ""
    assert sr["source"] == "unknown_src"  # 미등록 출처는 id 그대로


def test_chunk_url_fallback_to_source_site():
    # 문서 source_url이 없으면 출처 기관 공식 사이트로 폴백(근거 확인 링크 보장)
    sr = chunk_to_search_result({"chunk_id": "c3", "content": "x", "source_id": "mfds"})
    assert sr["url"] == "https://nedrug.mfds.go.kr" and "mfds.go.kr" in sr["display_link"]
    # 문서 원문 URL이 있으면 그게 우선
    sr2 = chunk_to_search_result(
        {"chunk_id": "c4", "content": "x", "source_id": "mfds", "source_url": "https://ex.kr/doc"})
    assert sr2["url"] == "https://ex.kr/doc"


# ─────────────────────── 인증 어댑터 ───────────────────────

def _make_jwt(payload: dict, secret: str = None) -> str:
    def b64(b):
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps(payload).encode())
    signing = f"{header}.{body}".encode()
    sig = hmac.new((secret or "x").encode(), signing, hashlib.sha256).digest() if secret else b"bad"
    return f"{header}.{body}.{b64(sig)}"


def test_trust_header_priority():
    user = resolve_user({"X-User-Id": "u1", "X-User-Name": "%ED%99%8D",
                         "X-User-Role": "tester"})
    assert user["id"] == "u1" and user["_auth"] == "trust_header"
    assert user["name"] == "홍"  # URL 디코딩


def test_bearer_verified_with_secret(monkeypatch):
    monkeypatch.setenv("RAG_JWT_SECRET", "topsecret")
    token = _make_jwt({"sub": "user-9", "name": "김환자", "role": "tester"}, "topsecret")
    user = resolve_user({"Authorization": f"Bearer {token}"})
    assert user and user["id"] == "user-9" and user["_auth"] == "bearer"
    assert user["name"] == "김환자"


def test_bearer_bad_signature_rejected(monkeypatch):
    monkeypatch.setenv("RAG_JWT_SECRET", "topsecret")
    token = _make_jwt({"sub": "user-9"}, "wrong-secret")
    assert resolve_user({"Authorization": f"Bearer {token}"}) is None


def test_bearer_rejected_without_secret_by_default(monkeypatch):
    monkeypatch.delenv("RAG_JWT_SECRET", raising=False)
    monkeypatch.delenv("RAG_ALLOW_UNVERIFIED_BEARER", raising=False)
    token = _make_jwt({"sub": "user-9"})
    assert resolve_user({"Authorization": f"Bearer {token}"}) is None  # 보안 기본값


def test_bearer_unverified_only_with_optin(monkeypatch):
    monkeypatch.delenv("RAG_JWT_SECRET", raising=False)
    monkeypatch.setenv("RAG_ALLOW_UNVERIFIED_BEARER", "1")
    token = _make_jwt({"user_id": "dev-1"})
    user = resolve_user({"Authorization": f"Bearer {token}"})
    assert user and user["id"] == "dev-1"


def test_malformed_bearer():
    assert decode_bearer("not.a.jwt.really") is None
    assert decode_bearer("") is None
    assert resolve_user({}) is None


# ─────────────────────── Vital Signs 파서 ───────────────────────

_VS_EXAMPLE = ('[{"bpm": 72, "spo2": 98, "bpd": 120, "bps": 80, '
               '"fever": 36.5, "stress": 3, "create_date": "2026-03-11 14:59:00"}]')


def test_parse_vital_signs_pdf_example():
    """원본 PDF 예시 그대로 파싱."""
    recs = parse_vital_signs(_VS_EXAMPLE)
    assert len(recs) == 1
    r = recs[0]
    assert r["bpm"] == 72 and r["spo2"] == 98 and r["fever"] == 36.5
    assert r["create_date"] == "2026-03-11 14:59:00"


def test_out_of_range_values_dropped():
    """물리적으로 불가능한 센서값(아티팩트)은 필드 단위로 격리."""
    recs = parse_vital_signs('[{"bpm": 9999, "spo2": 97}]')
    assert len(recs) == 1
    assert "bpm" not in recs[0] and recs[0]["spo2"] == 97


def test_invalid_json_returns_empty():
    assert parse_vital_signs("not json") == []
    assert parse_vital_signs("") == []


def test_parse_agent_inputs_full():
    parsed = parse_agent_inputs({
        "Vital Signs": _VS_EXAMPLE,
        "Air Quality Score": "72",
        "PHR": "{}",
    })
    assert len(parsed["vital_signs"]) == 1
    assert parsed["air_quality"] == "72"
    assert parsed["phr"] is None            # '{}'는 빈 값으로 간주
    assert "Vital Signs" in parsed["received_fields"]


def test_parse_agent_inputs_none():
    parsed = parse_agent_inputs(None)
    assert parsed["vital_signs"] == [] and parsed["received_fields"] == []


def test_audit_summary_has_no_raw_values():
    """감사 요약에는 원시 측정값이 포함되지 않는다 (개인정보 최소화)."""
    parsed = parse_agent_inputs({"Vital Signs": _VS_EXAMPLE, "Air Quality Score": "72"})
    summary = summarize_for_audit(parsed)
    assert "vitals=1건" in summary
    assert "72" not in summary.replace("vitals=1건", "")  # 측정값 미노출
    assert "36.5" not in summary
