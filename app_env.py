"""런타임 환경 판정 — 보안 fail-closed 가드 공용 헬퍼.

APP_ENV=prod(또는 production) 이면 프로덕션. 미설정=dev. BFF 토큰비밀·CI HMAC 키·
PASS provider 등 보안 설정의 '프로덕션에서 누락 시 차단' 판정에 사용.
"""
import os


def is_prod() -> bool:
    return os.environ.get("APP_ENV", "dev").strip().lower() in ("prod", "production")
