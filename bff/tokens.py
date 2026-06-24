"""
세션 토큰 — stdlib HMAC 서명(PyJWT 비의존). access 토큰만; refresh 는 DB(account_db).

토큰 형식: base64url(payload_json).base64url(HMAC-SHA256(body)). payload={sub,sid,iat,exp}.
검증은 상수시간 비교 + 만료 확인. 비밀키 = env BFF_TOKEN_SECRET(프로덕션 필수).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Dict, Optional

_DEV_SECRET = "dev-insecure-secret-change-me"


def _secret() -> bytes:
    return os.environ.get("BFF_TOKEN_SECRET", _DEV_SECRET).encode("utf-8")


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    return _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())


def issue_access_token(subject_id: str, *, session_id: Optional[str] = None,
                       ttl_seconds: int = 900, now: Optional[int] = None,
                       extra: Optional[Dict] = None) -> str:
    """단명 access 토큰 발급(기본 15분)."""
    iat = int(now if now is not None else time.time())
    payload = {"sub": subject_id, "sid": session_id, "iat": iat, "exp": iat + ttl_seconds}
    if extra:
        payload.update(extra)
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def verify_access_token(token: str, *, now: Optional[int] = None) -> Optional[Dict]:
    """유효하면 payload dict, 아니면 None. 서명 위조·만료·변조를 전부 거부."""
    if not token or not isinstance(token, str) or token.count(".") != 1:
        return None
    body, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(body)):   # 상수시간 비교
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    ts = int(now if now is not None else time.time())
    if int(payload.get("exp", 0)) <= ts:            # 만료
        return None
    return payload


def new_refresh_token() -> str:
    """예측 불가 refresh 토큰(원본은 클라이언트만, 서버는 해시 저장)."""
    return _b64e(os.urandom(32))


def hash_token(raw: str) -> str:
    """refresh 토큰 해시(DB 저장용)."""
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()
