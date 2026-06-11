"""
conversation_serializer.py — 우리 행(row) → Phoenix 대화관리 API 응답 객체 변환.

계약: docs/api/COMPAT-conversations.md (Conversations_20260608.pdf 기준).
- conversations 행 → Conversation (목록: chats=null / 상세: chats 포함)
- rag_queries 행   → Chat (input_state/output_state/SearchResult)
- 검색 매칭 텍스트 → snippet (100~200자, 매칭 주변)

전부 순수 함수 — DB 불필요, 단위테스트 가능.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional


def _iso(val) -> Optional[str]:
    """datetime/문자열 → ISO 8601 문자열 (None 안전)."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def citation_to_search_result(cit: Dict) -> Dict:
    """rag_queries.citations_json 항목 → Phoenix SearchResult(WEBPAGE 최소형).

    citations에는 본문이 없으므로 title/url 중심의 축약형으로 만든다
    (output_state.search_results — 이력 조회용이라 충분).
    """
    chunk_id = cit.get("chunk_id") or ""
    url = cit.get("source_url") or ""
    return {
        "strid": chunk_id,
        "content_type": "WEBPAGE",
        "source_type": "WEB",
        "title": cit.get("title") or "",
        "date": None,
        "cached_result_strid": None,
        "relevant_chunks": [],
        "url": url,
        "snippet": "",
        "source": cit.get("source_id") or "",
        "pdf_urls": [],
        "display_link": (url.split("/")[2] if url.startswith("http") and len(url.split("/")) > 2 else ""),
        "favicon": "",
    }


def rag_query_to_chat(row: Dict) -> Dict:
    """rag_queries 행 → Phoenix Chat 객체."""
    response_text = row.get("response_text") or ""
    citations: List[Dict] = []
    raw_cit = row.get("citations_json")
    if raw_cit:
        try:
            citations = json.loads(raw_cit) if isinstance(raw_cit, str) else (raw_cit or [])
        except Exception:
            citations = []

    output_state = None
    if response_text:
        output_state = {
            "response": response_text,
            "search_results": [citation_to_search_result(c) for c in citations],
        }

    return {
        "strid": row.get("id") or "",
        "status": "SUCCESS" if response_text else "FAILURE",
        "input_state": {"query": row.get("query_text") or ""},
        "output_state": output_state,
        "start_time": _iso(row.get("created_at")),
        "end_time": _iso(row.get("created_at")),
        "stream_messages": None,
    }


def conversation_to_dict(
    row: Dict,
    num_chats: int = 0,
    last_query: str = "",
    chats: Optional[List[Dict]] = None,
) -> Dict:
    """conversations 행 → Phoenix Conversation 객체.

    Args:
        row:        conversations 행 (display_status 등 011 컬럼 포함)
        num_chats:  해당 대화의 rag_queries 수 (목록 SQL에서 계산)
        last_query: 최신 질의 텍스트 (last_input_kwargs용)
        chats:      상세 조회 시 Chat 리스트, 목록에선 None (원본 규약)
    """
    strid = row.get("conversation_strid") or row.get("id") or ""
    return {
        "strid": strid,
        "title": row.get("title") or "",
        "display_type": row.get("display_type") or "SEARCH",
        "display_status": row.get("display_status") or "ACTIVE",
        "num_chats": int(num_chats or 0),
        "creation_time": _iso(row.get("created_at")),
        "last_used_time": _iso(row.get("updated_at")) or _iso(row.get("created_at")),
        "project_strid": row.get("project_strid"),
        "parent_conversation_strid": row.get("parent_conversation_strid"),
        "conversation_metadata": {"document_strid": None, "source_type": None},
        "last_input_kwargs": {"query": last_query or ""},
        "chats": chats,
    }


def build_snippet(text: str, search_query: str, width: int = 150) -> str:
    """매칭 텍스트에서 검색어 주변 100~200자 발췌 (원본 snippet 규약)."""
    text = (text or "").strip()
    if not text:
        return ""
    q = (search_query or "").strip()
    idx = text.lower().find(q.lower()) if q else -1
    if idx < 0:
        out = text[:width]
        return out + ("…" if len(text) > width else "")
    half = width // 2
    start = max(0, idx - half)
    end = min(len(text), idx + len(q) + half)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def toast(code: str, text: str, severity: str = "ERROR") -> Dict:
    """Phoenix Toast 객체."""
    return {"code": code, "metadata": {}, "alternate_text": text, "severity": severity}


# 정렬 파라미터 → 컬럼 매핑 (SQL 인젝션 차단 — 화이트리스트)
SORT_COLUMNS = {
    "title": "title",
    "last_used_time": "updated_at",
    "creation_time": "created_at",
}


def resolve_sort(sort_by: str, ascending: bool, default: str = "last_used_time") -> str:
    """정렬 파라미터 → 'ORDER BY <col> <dir>' 안전 조각."""
    col = SORT_COLUMNS.get(sort_by or default, SORT_COLUMNS[default])
    return f"{col} {'ASC' if ascending else 'DESC'}"
