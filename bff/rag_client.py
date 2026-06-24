"""
BFF → RAG 서비스 프록시. Cloud Run 메타데이터 SA 토큰(audience=RAG URL) 재사용.

RAG `/api/service/conversations/{graph}` 는 **SSE**(data: {...} 이벤트 스트림)다.
chat() 는 그 스트림을 소비해 GENERATION 텍스트를 모아 최종 답변으로 돌려준다.
동의 게이트 결과를 (1) 헤더(X-Personalization·X-Cross-Border-Ack)와 (2) payload
`personal_consent`(RAG G2 게이트)로 전달한다. 원시값·진단명은 절대 전달하지 않음
— agent_input_field_to_value 는 P0 에서 비움(PHR=P2). 테스트는 parse_sse_answer
(순수)와 urlopen 모킹으로 검증.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, Optional

RAG_URL = os.environ.get("RAG_URL", "").rstrip("/")
RAG_GRAPH = os.environ.get("RAG_GRAPH", "SUPERVISED_HYBRID_SEARCH")


def _id_token(audience: str) -> Optional[str]:
    """Cloud Run SA ID 토큰 — persona_test_server 의 검증된 로직 재사용(런타임 한정 lazy import)."""
    try:
        from persona_test_server import get_id_token
        return get_id_token(audience=audience)
    except Exception:
        return None


def _headers(user_id: Optional[str] = None, user_name: Optional[str] = None) -> Dict[str, str]:
    from urllib.parse import quote
    # X-User-* = RAG resolve_user(신뢰헤더). SA Bearer 는 Cloud Run IAM(run.invoke)용 — 별개.
    h = {
        "Content-Type": "application/json",
        "X-User-Id": user_id or "bff-user",
        "X-User-Name": quote(user_name or "마이헬스케어 사용자"),
        "X-User-Role": "user",
    }
    secret = os.environ.get("RAG_TRUST_SECRET")
    if secret:
        h["X-Rag-Trust"] = secret
    if ".run.app" in RAG_URL:               # 클라우드 대상이면 IAM 토큰
        tok = _id_token(RAG_URL)
        if tok:
            h["Authorization"] = f"Bearer {tok}"
    return h


def parse_sse_answer(raw: str) -> Dict:
    """RAG SSE 텍스트 → {answer, [citations·handoff·personal_injected…], [error]} (순수).

    인용 출처는 **INFO 이벤트의 data.search_results**로 온다(STOP 아님). 답변 본문의
    [n] 마커가 citations[n-1] 에 대응 → 프론트가 클릭형 출처 링크로 렌더.
    """
    parts = []
    meta: Dict = {}
    citations = []
    err = None
    for block in (raw or "").split("\n\n"):
        line = block.strip()
        if not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        t = ev.get("type")
        if t == "GENERATION":
            parts.append(ev.get("text") or "")
        elif t == "INFO":
            srs = (ev.get("data") or {}).get("search_results")
            if srs:
                citations = srs                 # 최신 검색결과로 갱신
        elif t == "STOP":
            for k in ("handoff", "personal_injected", "disclaimers", "action"):
                if k in ev:
                    meta[k] = ev[k]
        elif t == "ERROR":
            err = ev.get("message") or "rag_error"
    out: Dict = {"answer": "".join(parts).strip()}
    if citations:
        out["citations"] = [
            {"n": i + 1,
             "source": c.get("source") or c.get("title") or "출처",
             "title": c.get("title") or "",
             "url": c.get("url") or "",
             "snippet": (c.get("snippet") or "")[:160]}
            for i, c in enumerate(citations)
        ]
    out.update(meta)
    if err and not out["answer"]:
        out["error"] = err
    return out


def chat(message: str, *, conversation_id: Optional[str] = None,
         personalization: bool = False, cross_border_ack: bool = False,
         user_id: Optional[str] = None, user_name: Optional[str] = None,
         timeout: int = 120) -> Dict:
    """RAG 의료 채팅 호출(SSE 소비). 동의 게이트 결과를 헤더 + personal_consent 로 전달."""
    if not RAG_URL:
        return {"error": "RAG_URL_not_configured"}
    url = f"{RAG_URL}/api/service/conversations/{RAG_GRAPH}"
    payload = json.dumps({
        "query": message,
        "conversation_strid": conversation_id or "",
        "source_types": ["WEB"],
        "agent_input_field_to_value": {},      # P0: 개인 신호 비주입(PHR=P2)
        "personal_consent": bool(personalization),
    }, ensure_ascii=False).encode("utf-8")
    headers = _headers(user_id=user_id, user_name=user_name)
    headers["X-Personalization"] = "on" if personalization else "off"
    headers["X-Cross-Border-Ack"] = "1" if cross_border_ack else "0"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8", "replace")
    except Exception as e:
        return {"error": "rag_unreachable", "detail": str(e)[:200]}
    return parse_sse_answer(raw)
