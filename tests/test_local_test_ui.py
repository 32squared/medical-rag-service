"""
local_test_ui 스모크 — 모듈 구조 검증(네트워크/gcloud 불요).
"""

import local_test_ui as ui


def test_page_html_present():
    assert "<html" in ui.PAGE.lower()
    assert "/chat" in ui.PAGE          # 프록시 엔드포인트 참조
    assert "GENERATION" in ui.PAGE     # SSE 이벤트 파싱


def test_user_headers_shape():
    h = ui._user_headers("tok123")
    assert h["Authorization"] == "Bearer tok123"
    assert h["Content-Type"] == "application/json"
    for k in ("X-User-Id", "X-User-Name", "X-User-Role", "X-User-Permissions"):
        assert k in h


def test_default_rag_url_is_https():
    assert ui.DEFAULT_RAG_URL.startswith("https://")


def test_handler_defined():
    assert hasattr(ui, "Handler")
    assert hasattr(ui.Handler, "do_GET")
    assert hasattr(ui.Handler, "do_POST")
