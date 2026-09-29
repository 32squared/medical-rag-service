"""
tests/test_public_hub.py — 공개 허브(/hub)·시각화(/graph/*) 라우트 검증.

persona_test_server 핸들러를 소켓 없이 구동해 응답 캡처(네트워크 불요).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import persona_test_server as pts


class _Capture(pts.Handler if hasattr(pts, "Handler") else object):
    """BaseHTTPRequestHandler 초기화(소켓) 없이 do_GET만 구동."""

    def __init__(self, path):
        self.path = path
        self.rag_url = ""
        self.captured = None

    def _send(self, code, body, ctype="application/json"):
        self.captured = (code, body, ctype)


def _get(path):
    h = _Capture(path)
    h.do_GET()
    assert h.captured is not None, f"{path} 응답 없음"
    return h.captured


def test_hub_page_served():
    code, body, ctype = _get("/hub")
    assert code == 200
    assert "text/html" in ctype
    assert "마이헬스케어 Phase 3 프로토타이핑" in body
    # 두 섹션만: 라이브 서비스 + 인터랙티브 시각화 (내부 문서 섹션 없음)
    assert "라이브 서비스" in body and "인터랙티브 시각화" in body
    assert "기획 문서" not in body and "LAUNCH-READINESS" not in body
    # 상대 링크(같은 서비스)와 그래프 라우트
    assert 'href="/app"' in body and 'href="/graph/system"' in body and 'href="/graph/kb"' in body
    # 외부 공개 고지
    assert "의료 자문이 아닙니다" in body


def test_graph_pages_served():
    for route, marker in (("/graph/system", "RAG 시스템 그래프"),
                          ("/graph/kb", "KB 지식그래프")):
        code, body, ctype = _get(route)
        assert code == 200, route
        assert "text/html" in ctype
        assert marker in body
        assert "<svg" in body  # 독립실행 인터랙티브 문서


def test_trailing_slash_and_404():
    code, body, _ = _get("/hub/")
    assert code == 200
    code2, body2, _ = _get("/no-such-page")
    assert code2 == 404
