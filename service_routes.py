"""
service_routes.py — Phoenix `Run Graph Conversation` 호환 라우트 믹스인.

POST /api/service/conversations/{graph_type}  (SSE)
  → 요청 바디(query, conversation_strid, source_types, agent_input_field_to_value...)를
    우리 generate_response() 파이프라인에 연결하고, 이벤트를 phoenix_sse_adapter로
    원본 SSE 계약(INFO/PROGRESS/GENERATION/STOP/ERROR)으로 변환해 스트리밍한다.

설계 (COMPAT-run-graph.md §7):
- 기존 /api/rag/* 무변경 — additive 어댑터 계층.
- 인증: auth_resolver.resolve_user (신뢰헤더 우선 + Bearer JWT 수용).
- graph_type(SUPERVISED/ORCHESTRATED_HYBRID_SEARCH): 수신만, 동작 동일(단일 파이프라인).
- source_types(WEB/PUBMED): 수신만, 우리 KB 검색 사용 (MVP 정책 §4).
- agent_input_field_to_value: vital_input으로 파싱·감사 기록 (Phase 1에서 규칙엔진 연결).
- 드레인 모드: rag_routes._rag_chat과 동일 — 클라이언트 끊겨도 생성 완주(폴링 복구).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

import dbcommon as db
from rag_routes import RAG_ENABLED

_SERVICE_PATH_RE = re.compile(r'^/api/service/conversations/([A-Za-z_]+)$')

_KNOWN_GRAPH_TYPES = {"SUPERVISED_HYBRID_SEARCH", "ORCHESTRATED_HYBRID_SEARCH"}


class ServiceRoutesMixin:
    """Phoenix 호환 /api/service/* 디스패처. RagHandler의 베이스로 사용."""

    def _handle_service_route(self, method, path, parsed, body):
        m = _SERVICE_PATH_RE.match(path)
        if not m:
            return self._send_error(404, 'Not Found')
        if method != 'POST':
            return self._send_error(405, 'Method Not Allowed')
        return self._service_run_graph(m.group(1), body)

    # ────────────────────────────────────────────────────────
    def _service_run_graph(self, graph_type, body):
        """POST /api/service/conversations/{graph_type} — Run Graph 호환 SSE."""
        # 0) 피처 플래그 / 트러스트 시크릿
        if not RAG_ENABLED:
            return self._send_json(503, {
                "error": "RAG 기능이 현재 비활성화되어 있습니다.", "code": "RAG_DISABLED"})
        if not self._trust_ok():
            return self._send_error(403, '인증이 필요합니다 (trust secret 불일치)')

        # 1) 인증 — 신뢰헤더 우선 + Bearer 수용
        try:
            from auth_resolver import resolve_user
            user = resolve_user(self.headers)
        except Exception:
            user = self._get_tester_info()
        if not user:
            return self._send_error(403, '인증이 필요합니다 (신뢰헤더 또는 Bearer 토큰)')

        # 2) 요청 파싱
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
        except Exception as e:
            return self._send_json(400, {"error": f"Invalid JSON: {e}"})

        query = (payload.get('query') or '').strip()
        if not query:
            return self._send_json(400, {"error": "query is required"})

        conversation_id = (payload.get('conversation_strid') or '').strip() or str(uuid.uuid4())
        graph_type_norm = (graph_type or '').upper()
        if graph_type_norm not in _KNOWN_GRAPH_TYPES:
            self._add_log(f"[SERVICE] 미지의 graph_type={graph_type} — 기본 파이프라인으로 진행")

        # source_types/project_strid/agent_strid — 수신만 (MVP 정책)
        source_types = payload.get('source_types') or []
        agent_strid = payload.get('agent_strid') or ''

        # 개인화 입력 파싱 (Vital Signs / Air Quality / PHR) — 감사 기록
        from vital_input import parse_agent_inputs, summarize_for_audit
        personal = parse_agent_inputs(payload.get('agent_input_field_to_value'))
        self._add_log(
            f"[SERVICE] run_graph user={user['id']} graph={graph_type_norm} "
            f"sources={source_types} agent={agent_strid} {summarize_for_audit(personal)}"
        )

        # 3) PostgreSQL 모드 확인
        if not db._use_postgres:
            return self._send_json(503, {
                "error": "RAG features require PostgreSQL with pgvector.",
                "code": "RAG_REQUIRES_POSTGRES"})

        # 4) conversation 행 보장 (이력 표시용 — rag_routes._rag_chat과 동일 패턴)
        try:
            now_ts = datetime.now(timezone.utc).isoformat()
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"INSERT INTO conversations "
                    f"(id, user_id, user_name, title, env, conversation_strid, "
                    f"created_at, updated_at) "
                    f"VALUES ({db._ph(8)}) "
                    f"ON CONFLICT (id) DO NOTHING",
                    (conversation_id, user['id'], user.get('name', user['id']),
                     query[:80], 'rag', conversation_id, now_ts, now_ts),
                )
                conn.commit()
        except Exception as e:
            self._add_log(f"[SERVICE] conversation INSERT 오류 (무시): {e}")

        # 5) SSE 헤더
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('Connection', 'keep-alive')
        self._set_cors_headers()
        self.end_headers()

        try:
            self.connection.settimeout(30)
        except Exception:
            pass

        # 6) 스트리밍 — 우리 이벤트를 Phoenix 형식으로 변환해 emit
        from phoenix_sse_adapter import adapt_event, start_event

        def _emit(ev) -> bool:
            """이벤트 1건 전송. 실패(끊김) 시 False."""
            try:
                line = "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
                self.wfile.write(line.encode('utf-8'))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        client_gone = not _emit(start_event(conversation_id))
        stop_sent = False
        try:
            from rag_engine import generate_response
            for event in generate_response(
                query=query,
                conversation_id=conversation_id,
                provider_id=None,
                top_k=5,
                enable_guardrails=True,
            ):
                phoenix_events = adapt_event(event)
                for pev in phoenix_events:
                    if pev.get("type") == "STOP":
                        stop_sent = True
                    if client_gone:
                        continue  # 드레인 — 생성은 완주(결과 저장→폴링 복구)
                    if not _emit(pev):
                        client_gone = True
                        self._add_log("[SERVICE] 전송 중단(끊김/지연) — 생성은 끝까지 진행")
            if not stop_sent and not client_gone:
                _emit({"type": "STOP"})
            if client_gone:
                self._add_log("[SERVICE] 생성 완주 — 결과 저장됨(폴링 복구 가능)")
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            self._add_log(f"[SERVICE] 연결 오류: {e}")
        except Exception as e:
            self._add_log(f"[SERVICE] 스트리밍 오류: {e}")
            if not client_gone and not stop_sent:
                _emit({"type": "ERROR", "message": "answer generation failed"})
                _emit({"type": "STOP"})
