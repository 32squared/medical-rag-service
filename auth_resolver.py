"""
auth_resolver.py — 이중 인증 어댑터 (신뢰헤더 우선 + Bearer JWT 수용).

COMPAT-run-graph.md §6 결정: 인증 방식을 호출자가 확정하지 못한 상황이므로
서버가 둘 다 수용한다.

우선순위:
  1. 신뢰헤더 (X-User-Id 등) — 호스트/게이트웨이가 검증 후 주입하는 현행 모델
  2. Authorization: Bearer <JWT> — 클라이언트 직접 호출용
     - RAG_JWT_SECRET 설정 시: HS256 서명 검증 (표준 라이브러리 hmac — 외부 의존 없음)
     - 미설정 시: 기본 거부. RAG_ALLOW_UNVERIFIED_BEARER=1 일 때만 서명 미검증 수용
       (개발/테스트 전용 — 운영 금지)

resolve_user()는 헤더 dict만 받는 순수 함수 — 단위테스트 가능.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# JWT claim에서 사용자 id로 쓸 후보 (우선순위순)
_ID_CLAIMS = ("user_id", "sub", "uid", "user_strid", "email")
_NAME_CLAIMS = ("name", "user_name", "nickname")
_ROLE_CLAIMS = ("role", "user_role")


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _verify_hs256(signing_input: bytes, signature: bytes, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return hmac.compare_digest(expected, signature)


def decode_bearer(token: str, secret: str = None, allow_unverified: bool = None) -> Optional[Dict]:
    """JWT 토큰 → claims dict. 검증 실패/형식 오류면 None.

    Args:
        token:            'Bearer ' 제거된 JWT 문자열
        secret:           HS256 시크릿 (기본: env RAG_JWT_SECRET)
        allow_unverified: 시크릿 없을 때 미검증 수용 여부 (기본: env RAG_ALLOW_UNVERIFIED_BEARER)
    """
    secret = secret if secret is not None else os.environ.get("RAG_JWT_SECRET", "")
    if allow_unverified is None:
        allow_unverified = os.environ.get(
            "RAG_ALLOW_UNVERIFIED_BEARER", ""
        ).lower() in ("1", "true", "yes")

    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    try:
        payload = json.loads(_b64url_decode(payload_b64))
        if not isinstance(payload, dict):
            return None
    except Exception:
        return None

    if secret:
        try:
            header = json.loads(_b64url_decode(header_b64))
            if (header.get("alg") or "").upper() != "HS256":
                logger.warning("[auth] 지원하지 않는 JWT alg=%s", header.get("alg"))
                return None
            signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
            if not _verify_hs256(signing_input, _b64url_decode(sig_b64), secret):
                logger.warning("[auth] JWT 서명 검증 실패")
                return None
        except Exception as e:
            logger.warning("[auth] JWT 검증 오류: %s", e)
            return None
        return payload

    if allow_unverified:
        logger.warning("[auth] 미검증 Bearer 수용 (RAG_ALLOW_UNVERIFIED_BEARER — 운영 금지)")
        return payload

    logger.info("[auth] Bearer 수신했으나 RAG_JWT_SECRET 미설정 — 거부")
    return None


def _claims_to_user(claims: Dict) -> Optional[Dict]:
    """JWT claims → 우리 tester_info 형태 (rag_routes가 기대하는 dict)."""
    uid = next((str(claims[k]) for k in _ID_CLAIMS if claims.get(k)), "")
    if not uid:
        return None
    name = next((str(claims[k]) for k in _NAME_CLAIMS if claims.get(k)), uid)
    role = next((str(claims[k]) for k in _ROLE_CLAIMS if claims.get(k)), "tester")
    return {"id": uid, "alias": name, "name": name, "org": "",
            "uid": uid, "role": role, "_auth": "bearer"}


def resolve_user(headers: Dict[str, str]) -> Optional[Dict]:
    """헤더 → 사용자 정보 (신뢰헤더 우선, 폴백 Bearer). 실패 시 None.

    Args:
        headers: 대소문자 무관 조회 가능한 매핑 (http.server의 self.headers 호환)
    """
    get = headers.get  # http.client.HTTPMessage.get은 대소문자 무관

    # 1) 신뢰헤더 (현행 모델)
    uid = (get("X-User-Id") or "").strip()
    if uid:
        from urllib.parse import unquote
        name = unquote(get("X-User-Name") or "") or uid
        return {"id": uid, "alias": name, "name": name, "org": "",
                "uid": uid, "role": get("X-User-Role") or "tester",
                "_auth": "trust_header"}

    # 2) Bearer JWT
    authz = (get("Authorization") or "").strip()
    if authz.lower().startswith("bearer "):
        claims = decode_bearer(authz[7:].strip())
        if claims:
            return _claims_to_user(claims)

    return None
