"""
wraith_sse_adapter.py — 우리 SSE 이벤트 → wraith(Run Graph) SSE 이벤트 변환.

원본 계약: docs/api/COMPAT-run-graph.md (Run_Graph_Conversation_20260508.pdf 기준).
우리 generate_response()의 이벤트(INFO/EVIDENCE_CHECK/GENERATION/KEEP_ALIVE/STOP/ERROR)를
wraith 프론트가 기대하는 형식으로 재방출한다.

핵심 차이 처리:
- 연결 직후 INFO{graph_usage_strid, conversation_strid} 발급 (start_event)
- 우리 search_results(청크) → wraith SearchResult(WEBPAGE 형태) 매핑
- 우리 EVIDENCE_CHECK → wraith PROGRESS(label=evidence_check)로 래핑
- 우리 STOP{text,citations,tokens,...} → INFO(token_usage) + 빈 STOP 신호로 분해
- ERROR 뒤에는 STOP이 따라온다(원본 규약)

전부 순수 함수 — DB/네트워크 불필요, 단위테스트 가능.
"""

from __future__ import annotations

import os
import uuid
from typing import Dict, List

# source_id → 사용자 표시명 (SearchResult.source 필드용, 미등록은 source_id 그대로)
_SOURCE_DISPLAY = {
    "health_kdca": "질병관리청 국가건강정보포털",
    "kdca_api": "질병관리청 감염병포털",
    "nip": "질병관리청 예방접종도우미",
    "mfds": "식약처 의약품안전나라",
    "mfds_dur": "식약처 DUR",
    "mfds_drug_info": "식약처 e약은요",
    "nemc": "응급의료포털 E-Gen",
    "kr_law": "국가법령정보센터",
    "vital_refs": "공인 참조범위",
    "lifecycle_kr": "공공 건강정보",
    "navigation_kr": "의료 이용 안내",
    "safety_kr": "가정 안전·응급 정보",
    "consultation_seed": "의료진 작성 콘텐츠",
    "kmle_seed": "대한의학회 발췌",
    "internal_md": "의료진 작성 콘텐츠",
}

# source_id → 출처 기관 공식 사이트 (문서별 source_url이 비었을 때 폴백 링크).
# 정확한 원문 URL은 KB ingest 시 d.source_url에 채워야 함(D1). 내부/seed 출처는 공개 URL 없음.
_SOURCE_URL = {
    "health_kdca": "https://health.kdca.go.kr",
    "kdca_api": "https://www.kdca.go.kr",
    "nip": "https://nip.kdca.go.kr",
    "mfds": "https://nedrug.mfds.go.kr",
    "mfds_dur": "https://nedrug.mfds.go.kr",
    "mfds_drug_info": "https://nedrug.mfds.go.kr",
    "nemc": "https://www.e-gen.or.kr",
    "kr_law": "https://www.law.go.kr",
}


def new_usage_strid(conversation_id: str) -> str:
    """graph_usage_strid 생성 — 원본 예시 형식: '{conversation_uuid}_{uuid}'."""
    return f"{conversation_id}_{uuid.uuid4()}"


def start_event(conversation_id: str, usage_strid: str = None) -> Dict:
    """연결 직후 첫 INFO 이벤트 (원본 Example 1)."""
    return {
        "type": "INFO",
        "data": {
            "graph_usage_strid": usage_strid or new_usage_strid(conversation_id),
            "conversation_strid": conversation_id,
        },
    }


def chunk_to_search_result(chunk: Dict) -> Dict:
    """우리 검색 청크(_format_search_result) → wraith SearchResult(WEBPAGE 형태).

    KB 청크에는 논문 전용 필드(doi/authors 등)가 없으므로 WEBPAGE로 통일한다
    (COMPAT-run-graph.md §3.1). 프론트가 ARTICLE 카드를 요구하면 후속 조정.
    """
    chunk_id = chunk.get("chunk_id") or ""
    source_id = chunk.get("source_id") or ""
    content = chunk.get("content") or ""
    # 문서별 원문 URL 우선, 없으면 출처 기관 공식 사이트로 폴백(근거 확인 링크 보장)
    url = chunk.get("source_url") or _SOURCE_URL.get(source_id, "")
    return {
        "strid": chunk_id,
        "content_type": "WEBPAGE",
        "source_type": "WEB",
        "title": chunk.get("title") or "",
        "date": None,
        "cached_result_strid": None,
        "relevant_chunks": [{
            "strid": f"{chunk_id}_chunk_0",
            "type": "md",
            "chunk_index": 0,
            "chunk_text": content,
            "start_offset": -1,
            "end_offset": -1,
        }],
        "url": url,
        "snippet": content[:200],
        "source": _SOURCE_DISPLAY.get(source_id, source_id),
        "pdf_urls": [],
        "display_link": (url.split("/")[2] if url.startswith("http") and len(url.split("/")) > 2 else ""),
        "favicon": "",
    }


def _evidence_check_to_progress(ev: Dict) -> Dict:
    """우리 EVIDENCE_CHECK → wraith PROGRESS (정보 손실 없이 metadata에 보존)."""
    d = ev.get("data", {}) or {}
    return {
        "type": "PROGRESS",
        "strid": "evidence_check",
        "status": "SUCCESS",
        "level": 0,
        "display_message": (
            f"근거 검증: {d.get('quality', '')} ({d.get('decision', '')}, "
            f"관련 청크 {d.get('relevant_count', 0)}건)"
        ),
        "metadata": {"label": "evidence_check", **d},
        "result_items": None,
    }


def _stop_to_events(ev: Dict) -> List[Dict]:
    """우리 STOP(최종 묶음) → wraith INFO(token_usage) + 빈 STOP.

    원본 STOP은 종료 신호만 갖는다. 우리 STOP의 부가정보(tokens 등)는
    INFO(token_usage)로 옮기고, citations는 GENERATION 본문 마커 + 앞선
    search_results로 프론트가 해석한다.
    """
    out: List[Dict] = []
    tokens = ev.get("tokens") or {}
    if tokens:
        model = os.environ.get("RAG_LLM_MODEL", "gpt-5.4-mini")
        ti = int(tokens.get("input") or 0)
        to = int(tokens.get("output") or 0)
        out.append({
            "type": "INFO",
            "data": {"token_usage": {model: {
                "input_tokens": ti, "output_tokens": to, "total_tokens": ti + to,
            }}},
        })
    stop = {"type": "STOP"}
    if ev.get("followups"):
        stop["followups"] = ev["followups"]   # 멀티턴 후속 질문 제안(있으면)
    if ev.get("personal_injected"):
        stop["personal_injected"] = ev["personal_injected"]   # 방향2 주입 밴드(관찰성)
    if ev.get("handoff"):
        stop["handoff"] = ev["handoff"]   # 핸드오프(코칭 버튼) 메타(있으면, P1)
    out.append(stop)
    return out


def adapt_event(ev: Dict) -> List[Dict]:
    """우리 이벤트 1건 → wraith 이벤트 0..N건 (순수 함수).

    호출 측은 반환 리스트를 순서대로 SSE로 emit한다.
    ERROR는 [ERROR, STOP]을 반환하므로 호출 측은 이후 STOP 중복 방지 필요
    (마지막 이벤트가 STOP이면 스트림 종료).
    """
    t = ev.get("type")

    if t == "GENERATION":
        return [{"type": "GENERATION", "text": ev.get("text", "")}]

    if t == "KEEP_ALIVE":
        return [{"type": "KEEP_ALIVE"}]

    if t == "INFO":
        data = ev.get("data", {}) or {}
        if "search_results" in data:
            return [{
                "type": "INFO",
                "data": {"search_results": [
                    chunk_to_search_result(c) for c in data.get("search_results", [])
                ]},
            }]
        # status:"started" 등 내부용 INFO는 PROGRESS로 (프론트 무해)
        if data.get("status") == "started":
            return [{
                "type": "PROGRESS",
                "strid": "pipeline_start",
                "status": "IN_PROGRESS",
                "level": 0,
                "display_message": "검색을 시작합니다",
                "metadata": {"label": "start"},
                "result_items": None,
            }]
        return [{"type": "INFO", "data": data}]

    if t == "EVIDENCE_CHECK":
        return [_evidence_check_to_progress(ev)]

    if t == "STOP":
        return _stop_to_events(ev)

    if t == "ERROR":
        return [
            {"type": "ERROR", "message": ev.get("message", "오류가 발생했습니다")},
            {"type": "STOP"},
        ]

    # 미지의 타입은 그대로 통과 (전방 호환)
    return [ev]
