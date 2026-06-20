"""conversation_serializer 단위 테스트 — DB/네트워크 불필요.

계약 기준: docs/api/COMPAT-conversations.md (wraith Conversations PDF).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conversation_serializer import (
    build_snippet,
    citation_to_search_result,
    conversation_to_dict,
    rag_query_to_chat,
    resolve_sort,
    toast,
)

_CONV_ROW = {
    "id": "conv-1", "user_id": "u1", "user_name": "홍", "title": "발열 문의",
    "env": "rag", "conversation_strid": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-06-11T01:00:00+00:00", "updated_at": "2026-06-11T02:00:00+00:00",
    "display_status": "ACTIVE", "display_type": "SEARCH",
    "project_strid": None, "parent_conversation_strid": None,
}


def test_conversation_shape_matches_wraith():
    c = conversation_to_dict(_CONV_ROW, num_chats=3, last_query="열이 나요")
    # 원본 Conversation 필수 필드 전부 존재
    for f in ("strid", "title", "display_type", "display_status", "num_chats",
              "creation_time", "last_used_time", "project_strid",
              "parent_conversation_strid", "conversation_metadata",
              "last_input_kwargs", "chats"):
        assert f in c, f"필드 누락: {f}"
    assert c["strid"] == "550e8400-e29b-41d4-a716-446655440000"  # strid 우선
    assert c["num_chats"] == 3
    assert c["last_input_kwargs"] == {"query": "열이 나요"}
    assert c["conversation_metadata"] == {"document_strid": None, "source_type": None}
    assert c["chats"] is None  # 목록 규약: 항상 null


def test_conversation_strid_falls_back_to_id():
    row = dict(_CONV_ROW, conversation_strid=None)
    assert conversation_to_dict(row)["strid"] == "conv-1"


def test_conversation_defaults_for_missing_columns():
    """011 마이그레이션 전 행(컬럼 없음)도 기본값으로 직렬화."""
    row = {"id": "c2", "title": "t", "created_at": "2026-01-01"}
    c = conversation_to_dict(row)
    assert c["display_status"] == "ACTIVE" and c["display_type"] == "SEARCH"
    assert c["last_used_time"] == "2026-01-01"  # updated_at 없으면 created_at


def test_chat_success_shape():
    chat = rag_query_to_chat({
        "id": "rq-1", "query_text": "열이 나요",
        "response_text": "발열은 …[1]",
        "citations_json": '[{"marker":"[1]","chunk_id":"c9","source_id":"health_kdca",'
                          '"title":"발열","source_url":"https://health.kdca.go.kr/x"}]',
        "created_at": "2026-06-11T01:00:00+00:00",
    })
    assert chat["strid"] == "rq-1"
    assert chat["status"] == "SUCCESS"
    assert chat["input_state"] == {"query": "열이 나요"}
    assert chat["output_state"]["response"].startswith("발열은")
    sr = chat["output_state"]["search_results"][0]
    assert sr["strid"] == "c9" and sr["url"].startswith("https://")
    assert chat["stream_messages"] is None


def test_chat_failure_when_no_response():
    chat = rag_query_to_chat({"id": "rq-2", "query_text": "q", "response_text": None,
                              "created_at": "2026-01-01"})
    assert chat["status"] == "FAILURE"
    assert chat["output_state"] is None


def test_chat_bad_citations_json_safe():
    chat = rag_query_to_chat({"id": "rq-3", "query_text": "q", "response_text": "r",
                              "citations_json": "{broken", "created_at": "x"})
    assert chat["output_state"]["search_results"] == []


def test_citation_to_search_result_minimal():
    sr = citation_to_search_result({"chunk_id": "c1", "title": "t", "source_url": ""})
    assert sr["content_type"] == "WEBPAGE" and sr["display_link"] == ""


def test_snippet_centers_on_match():
    text = "가" * 200 + "발열기준" + "나" * 200
    s = build_snippet(text, "발열")
    assert "발열기준" in s
    assert s.startswith("…") and s.endswith("…")
    assert len(s) <= 210


def test_snippet_no_match_truncates_head():
    s = build_snippet("짧은 본문입니다", "없는검색어")
    assert s == "짧은 본문입니다"


def test_snippet_empty():
    assert build_snippet("", "x") == ""


def test_resolve_sort_whitelist():
    assert resolve_sort("title", True) == "title ASC"
    assert resolve_sort("creation_time", False) == "created_at DESC"
    assert resolve_sort("last_used_time", False) == "updated_at DESC"
    # 인젝션 시도 → 기본 컬럼으로 폴백
    assert resolve_sort("1; DROP TABLE x", False) == "updated_at DESC"


def test_toast_shape():
    t = toast("NOT_FOUND_CONVERSATION", "없음")
    assert t == {"code": "NOT_FOUND_CONVERSATION", "metadata": {},
                 "alternate_text": "없음", "severity": "ERROR"}
