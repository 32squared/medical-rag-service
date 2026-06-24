"""
BFF → RAG 서비스 프록시. Cloud Run 메타데이터 SA 토큰(audience=RAG URL) 재사용.

chat() 는 동의 게이트 결과를 헤더(X-Personalization·X-Cross-Border-Ack)로 RAG 에
전달한다. 원시값·진단명은 절대 전달하지 않음 — RAG 내부 결정엔진이 비식별 라벨만 사용.
테스트는 이 함수를 모킹한다(네트워크 분리).
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, Optional

RAG_URL = os.environ.get("RAG_URL", "").rstrip("/")
RAG_GRAPH = os.environ.get("RAG_GRAPH", "medical_rag")


def _id_token(audience: str) -> Optional[str]:
    """Cloud Run SA ID 토큰 — persona_test_server 의 검증된 로직 재사용(런타임 한정 lazy import)."""
    try:
        from persona_test_server import get_id_token
        return get_id_token(audience=audience)
    except Exception:
        return None


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if ".run.app" in RAG_URL:               # 클라우드 대상이면 IAM 토큰
        tok = _id_token(RAG_URL)
        if tok:
            h["Authorization"] = f"Bearer {tok}"
    return h


def chat(message: str, *, conversation_id: Optional[str] = None,
         personalization: bool = False, cross_border_ack: bool = False,
         timeout: int = 30) -> Dict:
    """RAG 의료 채팅 호출. 게이트 결과를 헤더로 전달. 반환=RAG 응답(dict)."""
    if not RAG_URL:
        return {"error": "RAG_URL_not_configured"}
    url = f"{RAG_URL}/api/service/conversations/{RAG_GRAPH}"
    payload = json.dumps(
        {"message": message, "conversation_id": conversation_id},
        ensure_ascii=False,
    ).encode("utf-8")
    headers = _headers()
    headers["X-Personalization"] = "on" if personalization else "off"
    headers["X-Cross-Border-Ack"] = "1" if cross_border_ack else "0"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
