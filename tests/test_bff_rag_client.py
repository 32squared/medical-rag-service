"""test_bff_rag_client.py — BFF→RAG SSE 프록시(파싱 순수 + 페이로드/헤더)."""
import json


def test_parse_sse_citations_from_info_and_meta():
    from bff import rag_client as rc
    raw = ('data: {"type":"INFO","data":{"search_results":[{"source":"질병관리청","title":"두통","url":"https://h.kr/1"}]}}\n\n'
           'data: {"type":"GENERATION","text":"두통은 "}\n\n'
           'data: {"type":"GENERATION","text":"여러 원인이 있습니다 [1]."}\n\n'
           'data: {"type":"STOP","action":"answer"}\n\n')
    out = rc.parse_sse_answer(raw)
    assert out["answer"] == "두통은 여러 원인이 있습니다 [1]."
    assert out["citations"][0]["n"] == 1                         # INFO.search_results → 인용
    assert out["citations"][0]["source"] == "질병관리청"
    assert out["citations"][0]["url"] == "https://h.kr/1"
    assert out["action"] == "answer"


def test_parse_sse_no_citations_key_when_absent():
    from bff import rag_client as rc
    out = rc.parse_sse_answer('data: {"type":"GENERATION","text":"x"}\n\ndata: {"type":"STOP"}\n\n')
    assert "citations" not in out


def test_parse_sse_error_only():
    from bff import rag_client as rc
    out = rc.parse_sse_answer('data: {"type":"ERROR","message":"backend down"}\n\n')
    assert out["answer"] == "" and out["error"] == "backend down"


def test_chat_no_rag_url():
    from bff import rag_client as rc
    import bff.rag_client as m
    saved = m.RAG_URL
    m.RAG_URL = ""
    try:
        assert rc.chat("x")["error"] == "RAG_URL_not_configured"
    finally:
        m.RAG_URL = saved


def test_chat_builds_payload_and_consumes_sse(monkeypatch):
    import bff.rag_client as rc
    monkeypatch.setattr(rc, "RAG_URL", "http://rag.local")
    monkeypatch.setattr(rc, "RAG_GRAPH", "SUPERVISED_HYBRID_SEARCH")
    sse = (b'data: {"type":"INFO","data":{"search_results":[{"source":"KDCA","url":"https://k.kr"}]}}\n\n'
           b'data: {"type":"GENERATION","text":"hello "}\n\n'
           b'data: {"type":"GENERATION","text":"world [1]"}\n\n'
           b'data: {"type":"STOP"}\n\n')
    captured = {}

    class FakeResp:
        def read(self):
            return sse

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResp()

    monkeypatch.setattr(rc.urllib.request, "urlopen", fake_urlopen)
    out = rc.chat("질문있어요", conversation_id="c1", personalization=True)
    assert out["answer"] == "hello world [1]"
    assert out["citations"][0]["source"] == "KDCA"
    assert "SUPERVISED_HYBRID_SEARCH" in captured["url"]
    assert captured["body"]["query"] == "질문있어요"
    assert captured["body"]["conversation_strid"] == "c1"
    assert captured["body"]["personal_consent"] is True       # 동의게이트 → RAG G2
    assert captured["body"]["source_types"] == ["WEB"]


def test_chat_unreachable_returns_error(monkeypatch):
    import bff.rag_client as rc
    monkeypatch.setattr(rc, "RAG_URL", "http://rag.local")

    def boom(req, timeout=0):
        raise OSError("connection refused")

    monkeypatch.setattr(rc.urllib.request, "urlopen", boom)
    out = rc.chat("x")
    assert out["error"] == "rag_unreachable"
