"""
env_loader.py — 무의존 .env 로더.

python-dotenv 없이 프로젝트 루트의 `.env`(KEY=VALUE 라인)를 os.environ에 주입한다.
- 이미 설정된 환경변수는 덮어쓰지 않는다(실제 환경/배포 우선).
- `.env`는 .gitignore로 커밋 금지(시크릿).
- 진입점(rag_server.py, rag_try.py 등)에서 import 직후 load_env() 호출.
"""

from __future__ import annotations

import os

_REPO = os.path.dirname(os.path.abspath(__file__))


def load_env(path: str = None, override: bool = False) -> int:
    """`.env`를 읽어 os.environ에 주입. 주입한 키 수 반환(파일 없으면 0)."""
    path = path or os.path.join(_REPO, ".env")
    if not os.path.exists(path):
        return 0
    loaded = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if not key:
                    continue
                if override or key not in os.environ:
                    os.environ[key] = val
                    loaded += 1
    except Exception:
        return loaded
    return loaded
