#!/bin/sh
# medical-rag-service 진입점 (저장소 분리 후 — RAG 전용).
# RUN_MODE=migrate 면 DB 스키마 마이그레이션 1회 실행 후 종료 (Cloud Run Job 용),
# 그 외(기본)엔 RAG 독립 HTTP 서비스 상주.
# ※ 호스트 전용 모드(job/service → job_runner.py/proxy_server.py)는 분리 후 이 repo 에
#    해당 파일이 없으므로 제거했다. 호스트 배포는 medical-compliance-tester repo 가 담당.
set -e

if [ "$RUN_MODE" = "migrate" ]; then
    # --sync: 최초 baseline(현재 스키마 채택) 후 대기 마이그레이션 apply (멱등).
    echo "[entrypoint] mode=migrate → python /app/migrations/migrate_runner.py --sync"
    exec python /app/migrations/migrate_runner.py --sync
elif [ "$RUN_MODE" = "viewer" ]; then
    # 페르소나 테스트 뷰어(공개). PORT/0.0.0.0 바인딩은 persona_test_server.main()에서 처리.
    # RAG 대상은 RAG_DEV_URL(기본 CLOUD_DEV_URL), RAG 호출은 메타데이터 SA 토큰.
    echo "[entrypoint] mode=viewer → python /app/persona_test_server.py"
    exec python /app/persona_test_server.py
else
    # 기본 = RAG 독립 HTTP 서비스 — /api/rag/* 단독 서빙.
    PORT_USED="${PORT:-8080}"
    echo "[entrypoint] mode=rag → python /app/rag_server.py --port ${PORT_USED}"
    exec python /app/rag_server.py --port "${PORT_USED}"
fi
