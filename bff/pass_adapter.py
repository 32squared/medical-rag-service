"""
PASS 본인인증 어댑터 — P0. mock 구현(개발/테스트) + 실연동 인터페이스.

start_verification() → 인증창 트랜잭션. verify(tx_id, ...) → {ci, di, name}.
실 PASS(통신사) provider 는 동일 인터페이스로 교체. CI/DI 원본은 즉시 해시되어
account_db 에 저장(원본 비보관 — account_db.hash_ci).
"""
from __future__ import annotations

import hashlib
import os
import uuid as _uuid
from typing import Dict, Optional

from app_env import is_prod

PROVIDER = os.environ.get("PASS_PROVIDER", "mock")


def _assert_provider_allowed() -> None:
    """프로덕션에서 mock provider 는 명시 허용(ALLOW_MOCK_AUTH) 없으면 차단 — 신원위조 방지."""
    if PROVIDER == "mock" and is_prod() and not os.environ.get("ALLOW_MOCK_AUTH"):
        raise RuntimeError("mock PASS provider not allowed in production")


def start_verification(return_url: Optional[str] = None) -> Dict:
    """인증창 트랜잭션 시작 → tx_id + (실연동 시) 리다이렉트 정보."""
    _assert_provider_allowed()
    return {
        "tx_id": _uuid.uuid4().hex,
        "provider": PROVIDER,
        "redirect_url": return_url or "",
        "mock": PROVIDER == "mock",
    }


def verify(tx_id: str, *, mock_identity: Optional[str] = None) -> Dict:
    """
    인증 완료 → 신원(ci/di). mock 은 mock_identity(또는 tx_id)에서 결정적 CI 파생.
    실 provider 는 PASS 응답 파싱 — 미구성 시 NotImplementedError(보수적: 가짜 통과 금지).
    """
    _assert_provider_allowed()
    if PROVIDER != "mock":
        raise NotImplementedError("real PASS provider not configured")
    seed = mock_identity or tx_id or "anon"
    ci = "MOCKCI:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
    di = "MOCKDI:" + hashlib.sha256(("di:" + seed).encode("utf-8")).hexdigest()[:32]
    return {"ci": ci, "di": di, "name": None, "provider": "mock"}
