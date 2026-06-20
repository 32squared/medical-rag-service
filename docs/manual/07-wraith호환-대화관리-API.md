# 07. wraith 호환 / 대화관리 API

파트너 대화 플랫폼(**wraith**, 구 Phoenix)의 Run Graph·대화관리 계약에 맞춘 호환 계층.
기존 `/api/rag/*`는 무변경, additive로 얹는다.

- 코드: [`service_routes.py`](../../service_routes.py), [`wraith_sse_adapter.py`](../../wraith_sse_adapter.py), [`rag_history_routes.py`](../../rag_history_routes.py)
- 계약 문서: `docs/api/COMPAT-run-graph.md`, `docs/api/COMPAT-conversations.md`
- 선행 마이그레이션: 011(conversations 호환 컬럼), 014(projects)
- 테스트: `tests/test_wraith_compat.py`, `tests/test_conversation_serializer.py`

## A. Run Graph 대화 (개인화 진입점)

```
POST /api/service/conversations/{graph_type}     (SSE)
```

요청 바디:
```json
{
  "query": "혈압이 높게 나왔는데 괜찮을까요?",
  "conversation_strid": "...",
  "source_types": ["WEB"],
  "agent_input_field_to_value": {
    "Vital Signs": "[{\"bps\":152,\"bpd\":96,\"bpm\":78}]",
    "Air Quality Score": "보통",
    "PHR": "{}"
  }
}
```

처리:
1. `graph_type`(SUPERVISED/ORCHESTRATED_HYBRID_SEARCH)·`source_types`(WEB/PUBMED)는 **수신만**(단일 파이프라인).
2. `agent_input_field_to_value` → `vital_input.parse_agent_inputs` → `vital_rules.run`(+trends)·`env_rules` →
   **`_personal_findings`**(개인화). → 이 값이 `generate_response(personal_findings=...)`로 전달된다.
3. 우리 이벤트를 `wraith_sse_adapter`로 wraith 형식 SSE로 변환해 스트리밍.
4. 드레인 모드 — 끊겨도 생성 완주(폴링 복구).

### 인증
- `auth_resolver.resolve_user` — 신뢰헤더(X-User-*) 우선 + Bearer JWT 수용.
- 트러스트 시크릿: `RAG_TRUST_SECRET` 설정 시 `X-Rag-Trust` 헤더 일치 필요. **미설정이면 통과**(로컬).

> 페르소나 테스트 서버(03)의 `/chat`이 이 엔드포인트로 프록시한다.

## B. wraith SSE 어댑터

`wraith_sse_adapter.adapt_event(ev)` — 우리 이벤트 1건 → wraith 이벤트 0..N건(순수 함수).

| 우리 이벤트 | → wraith |
|---|---|
| 연결 직후 | INFO{graph_usage_strid, conversation_strid} (`start_event`) |
| GENERATION | GENERATION{text} |
| INFO(search_results) | INFO{search_results:[SearchResult(WEBPAGE)]} |
| INFO(status:started) | PROGRESS(pipeline_start) |
| EVIDENCE_CHECK | PROGRESS(evidence_check) |
| STOP | INFO(token_usage) + 빈 STOP |
| ERROR | ERROR + STOP |

## C. 대화관리 API (`/api/data_management/*`)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/conversations` | 목록(필터·정렬·페이지) |
| GET | `/conversations/search?search_query=` | 전문 검색(제목+채팅 본문) |
| GET | `/conversations/{strid}` | 상세(+chats) |
| PATCH | `/conversations/{strid}` | 수정(title/project_strid) |
| DELETE | `/conversations/{strid}` | 소프트 삭제(DELETED) |
| GET / POST | `/projects` | 프로젝트 목록 / 생성 |
| PATCH / DELETE | `/projects/{strid}` | 프로젝트 수정 / 소프트 삭제 |

- 모든 조회는 `user_id` 스코프. 인증은 A와 동일(신뢰헤더+Bearer, 트러스트).
- 직렬화는 순수 함수 `conversation_serializer`(conversation_to_dict·project_to_dict·rag_query_to_chat·build_snippet)에 위임.
- 소프트 삭제: 물리 삭제 대신 `display_status='DELETED'`.

## 라우팅 합성

`rag_server.RagHandler`가 믹스인을 합성한다:
```python
class RagHandler(HistoryRoutesMixin, ServiceRoutesMixin, RagRoutesMixin, ...):
    # /api/data_management/* → _handle_dm_route
    # /api/service/*         → _handle_service_route
    # /api/rag/*             → _handle_rag_route
```
