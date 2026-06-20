#!/usr/bin/env python
"""
setup_local_pg.py — PostgreSQL(pgvector) 준비 후 RAG를 end-to-end로 켜는 원커맨드 finisher.

전제: pgvector가 가능한 PostgreSQL이 있고 .env에 DATABASE_URL이 설정돼 있다
(클라우드 무료 PG[Neon/Supabase] 또는 Docker pgvector 또는 네이티브 설치).

수행:
  1) .env 로드 + DATABASE_URL/psycopg 확인
  2) 마이그레이션 --sync (CREATE EXTENSION vector 포함, 전 테이블 생성)
  3) KB 시드 적재 (+ OPENAI_API_KEY 있으면 임베딩 계산)
  4) 스모크: hybrid_search 실검색 1회 → 결과 건수 출력

사용:
  python setup_local_pg.py            # 전체
  python setup_local_pg.py --no-seed  # 마이그레이션·스모크만
"""

import os
import sys
import subprocess

_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def _step(msg):
    print("\n" + "=" * 60 + f"\n▶ {msg}\n" + "=" * 60)


def main():
    no_seed = "--no-seed" in sys.argv

    try:
        from env_loader import load_env
        load_env()
    except Exception:
        pass

    # 1) 전제 확인
    _step("1/4 전제 확인")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("✗ DATABASE_URL 미설정. .env에 다음을 넣으세요:")
        print("    DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        print("  (무료 PG: Neon/Supabase, 또는 Docker pgvector — docs/SETUP-PG.md 참고)")
        return 2
    safe = url.split("@")[-1] if "@" in url else url
    print(f"✓ DATABASE_URL = …@{safe}")
    try:
        import psycopg2  # noqa: F401
        print("✓ psycopg2 드라이버 존재")
    except Exception:
        print("✗ psycopg2 없음 → pip install -r requirements.txt")
        return 2
    print("✓ OPENAI_API_KEY:", "설정됨" if os.environ.get("OPENAI_API_KEY") else "없음(임베딩/생성 제한)")

    py = sys.executable

    # 2) 마이그레이션
    _step("2/4 마이그레이션 (--sync: extension + 전 테이블)")
    r = subprocess.run([py, "migrations/migrate_runner.py", "--sync"], cwd=_REPO)
    if r.returncode != 0:
        print("✗ 마이그레이션 실패 — DATABASE_URL 권한/pgvector 가용성 확인")
        return r.returncode

    # 3) KB 시드
    if not no_seed:
        _step("3/4 KB 시드 적재 (+ 임베딩)")
        r = subprocess.run([py, "seed_kb_expansion.py"], cwd=_REPO)
        if r.returncode != 0:
            print("⚠ 시드 일부 실패(계속 진행) — 로그 확인")
    else:
        _step("3/4 시드 건너뜀 (--no-seed)")

    # 4) 스모크: 실검색
    _step("4/4 스모크 — hybrid_search 실검색")
    try:
        from rag_engine import hybrid_search
        hits = hybrid_search("두통", top_k=3)
        print(f"✓ 검색 동작: '두통' → {len(hits)}건")
        for h in hits[:3]:
            print("   -", (h.get("title") or h.get("chunk_id") or "")[:50],
                  "| score=", round(float(h.get("score") or 0), 3))
        if not hits:
            print("  (0건 — 시드가 비었을 수 있음. seed_kb_expansion / collect_public_kb 확인)")
    except Exception as e:
        print(f"✗ 스모크 실패: {type(e).__name__}: {str(e)[:120]}")
        return 1

    _step("완료 — 이제 서버 실행")
    print("  python rag_server.py        # /api/rag/chat · /api/service/* · /api/data_management/*")
    print("  (또는 라이브 단발 테스트: docs/SETUP-PG.md 참고)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
