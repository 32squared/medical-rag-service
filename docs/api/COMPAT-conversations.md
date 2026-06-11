# 대화 관리 API — Phoenix Lab 호환 인터페이스 정의서

> 목적: 현재 사용 중인 RAG(Phoenix Lab / SKIX)의 **대화·프로젝트 관리 API**(`Conversations_20260608.pdf`)를
> 우리 `medical-rag-service`로 **드롭인 교체**하기 위한 호환 스펙. 프론트엔드를 수정하지 않고
> 베이스 URL만 우리 서비스로 바꿔도 동작하는 것을 목표로 한다.
>
> 기준: 원본 PDF 9개 엔드포인트(전부 `/api/data_management/*`) + 우리 데이터 모델 매핑.
> 작성: 2026-06-11.

---

## 0. 두 API 계층의 관계 (중요)

이 PDF가 정의하는 것은 **대화 이력 관리(data_management)** 계층이다. "질문을 보내 답변을 생성"하는
**실행/스트리밍** 계층은 이 문서에 없다(별도 엔드포인트 — Phoenix는 `/api/service/conversations/{graph_type}` 추정).

| 계층 | Phoenix(현행) | 우리(medical-rag-service) |
|---|---|---|
| 생성/스트리밍 | (이 PDF 밖) `/api/service/...` | `POST /api/rag/chat` (SSE) — [INTERFACE.md](INTERFACE.md) |
| **이력 관리** | **`/api/data_management/conversations`·`/projects`** | **본 문서에서 신규 정의(호환)** |

→ 즉, 우리는 (1) 기존 `/api/rag/chat`은 그대로 두고, (2) 본 문서의 `data_management` 호환 API를
**추가(additive)**하면 대화 목록·검색·상세·수정·삭제·프로젝트가 프론트 무수정으로 붙는다.

---

## 1. 공통 규약

- **베이스 경로**: `/api/data_management` (원본과 동일). 베이스 URL은 우리 서비스 호스트(§ INTERFACE.md 2).
- **인증**: 우리 신뢰헤더 모델 사용(`X-User-Id` 등 — [INTERFACE.md](INTERFACE.md) §3). 원본의 `user_strid` ↔ 우리 `X-User-Id`.
  - 리버스 프록시 뒤에서는 프론트가 보내던 쿠키/토큰을 프록시가 신뢰헤더로 변환 → 프론트 무수정.
- **응답 공통**: 목록/뮤테이션 응답에 `toast: Toast | null` 포함(원본과 동일).
- **시간 포맷**: ISO 8601 (`2026-06-08T10:30:00+00:00`).
- **식별자**: `strid` = UUID 문자열.

### Toast (공통 오류/알림 객체)
```json
{ "code": "NOT_FOUND_DOCUMENT", "metadata": {}, "alternate_text": "사용자 표시 문구", "severity": "ERROR" }
```
`severity` ∈ `ERROR | INFO | WARNING`. 정상 시 `toast: null`.

---

## 2. 데이터 모델 매핑

### 2.1 Conversation ↔ 우리 `conversations` + `rag_queries`

| 원본 필드 | 타입 | 우리 매핑 | 비고 |
|---|---|---|---|
| `strid` | UUID | `conversations.conversation_strid`(없으면 `id`) | 이미 컬럼 존재 |
| `title` | string | `conversations.title` | 첫 질의 80자 자동 |
| `display_type` | enum `SEARCH`\|`DOCUMENT_CHAT` | 고정 `"SEARCH"` | 의료 Q&A는 검색형 |
| `display_status` | enum `ACTIVE`\|`DELETED`\|`ARCHIVED` | **신규 컬럼** `display_status`(기본 `ACTIVE`) | 마이그레이션 필요 |
| `num_chats` | integer | `COUNT(rag_queries WHERE conversation_id=strid)` | 목록에선 계산값 |
| `creation_time` | datetime | `conversations.created_at` | |
| `last_used_time` | datetime | `conversations.updated_at` (또는 최신 `rag_queries.created_at`) | |
| `project_strid` | string\|null | **신규 컬럼** `project_strid`(기본 null) | 마이그레이션 필요 |
| `parent_conversation_strid` | string\|null | **신규 컬럼**(기본 null) | 계층 미사용 시 항상 null |
| `conversation_metadata` | object | `{document_strid: null, source_type: null}` | SEARCH형은 null |
| `last_input_kwargs` | object | `{query: <최신 rag_queries.query_text>}` | |
| `chats` | array\<Chat\>\|null | 목록에선 **항상 null**, 상세에서만 채움 | 원본 동일 규약 |

### 2.2 Chat ↔ 우리 `rag_queries`

| 원본 필드 | 타입 | 우리 매핑 |
|---|---|---|
| `strid` | string | `rag_queries.id` |
| `status` | enum | `SUCCESS`(행 존재+response_text 있음) / `FAILURE`(없음) / `IN_PROGRESS`(생성 중 — 현재는 폴링으로만 관측) |
| `input_state` | object | `{query: rag_queries.query_text}` |
| `output_state` | object\|null | `{response: response_text, search_results: <citations_json/retrieved_chunk_ids 변환>}` |
| `start_time` | datetime | `rag_queries.created_at` |
| `end_time` | datetime\|null | `created_at`(+`latency_total_ms` 가산 가능) |
| `stream_messages` | array\|null | `null` (현재 미저장) |

### 2.3 Project ↔ **신규 `projects` 테이블**

원본은 프로젝트(대화 그룹) 개념을 둔다. 우리는 미보유 → 신규 테이블로 호환 지원(미사용해도 엔드포인트는 존재).

| 원본 필드 | 우리 매핑(신규 `projects`) |
|---|---|
| `strid` | `id` (UUID) |
| `name` | `name` |
| `display_status` | `display_status` (`ACTIVE`/`DELETED`/`ARCHIVED`) |
| `creation_time` | `created_at` |
| `last_modified_time` | `updated_at` |
| `user_strid` | `user_id` (= X-User-Id) |

---

## 3. 엔드포인트 정의 (원본 시그니처 유지)

### 3.1 GET `/api/data_management/conversations` — 목록
쿼리: `project_strid`(string, `'null'`이면 미할당), `start_index`(int, 기본0), `sort_by`(`title`\|`last_used_time`\|`creation_time`, 기본 `last_used_time`), `ascending`(bool, 기본 false), `limit`(int\|null)
```json
{ "results": [ { /* Conversation, chats=null */ } ], "total_count": 0, "toast": null }
```
우리 구현: `conversations`에서 `user_id = X-User-Id AND display_status='ACTIVE'` 필터, 정렬·페이지네이션, `num_chats`는 서브쿼리 COUNT.

### 3.2 GET `/api/data_management/conversations/search` — 전문 검색
쿼리: `search_query`(필수, len≥1), `start_index`(0), `limit`(10), `deduplicate`(bool, false), `sort_by`(`last_used_time`\|`creation_time`\|null), `ascending`(false)
```json
{ "results": [ { "conversation": { /* Conversation */ }, "chat_strid": "…|null", "time": "…", "snippet": "…100~200자…" } ], "total_count": 0, "toast": null }
```
우리 구현: `conversations.title` + `rag_queries.query_text/response_text`에 ILIKE/tsvector 검색, 매칭 위치로 `snippet` 생성. `chat_strid`는 채팅 본문 매칭 시 해당 `rag_queries.id`, 제목만 매칭이면 null.

### 3.3 GET `/api/data_management/conversations/{conversation_strid}` — 상세(+chats)
경로: `conversation_strid`(UUID)
응답: Conversation **+ `chats: [Chat]`**(해당 대화의 `rag_queries`를 시간순으로 Chat 변환).

### 3.4 PATCH `/api/data_management/conversations/{conversation_strid}` — 수정
바디: `{ "title": "…|null", "project_strid": "…|null" }`
```json
{ "status": "success", "toast": null }
```

### 3.5 DELETE `/api/data_management/conversations/{conversation_strid}` — 삭제
**소프트 삭제 권장**: `display_status='DELETED'`로 갱신(원본도 DELETED 상태 보유). 응답 `{status, toast}`.

### 3.6 GET `/api/data_management/projects` — 프로젝트 목록
쿼리: `start_index`(0), `sort_by`(`name`\|`last_modified_time`\|`creation_time`, 기본 `creation_time`), `ascending`(false), `limit`(null)
```json
{ "results": [ { /* Project */ } ], "total_count": 0, "toast": null }
```

### 3.7 POST `/api/data_management/projects` — 생성
바디: `{ "name": "프로젝트명" }` → 응답: Project + `toast`.

### 3.8 PATCH `/api/data_management/projects/{project_strid}` — 수정
바디: `{ "name": "…" }` → `{status, toast}`.

### 3.9 DELETE `/api/data_management/projects/{project_strid}` — 삭제
소프트 삭제(`display_status='DELETED'`) → `{status, toast}`.

---

## 4. 필요한 스키마 변경 (additive · 멱등)

```sql
-- migrations/011_conversation_compat.sql (PG) + _sqlite 페어
-- conversations (호스트 소유) 보강 — 멱등
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS display_status TEXT DEFAULT 'ACTIVE';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS display_type   TEXT DEFAULT 'SEARCH';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS project_strid  TEXT;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS parent_conversation_strid TEXT;

-- projects 신규
CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    display_status  TEXT DEFAULT 'ACTIVE',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id, display_status);
CREATE INDEX IF NOT EXISTS idx_conv_user_status ON conversations(user_id, display_status);
```
> `conversations`는 "호스트 소유" 테이블이라는 분리 불변식이 있다([001 마이그레이션 §10 주석] 참고).
> 따라서 이 ALTER는 **호스트 마이그레이션 경로**로 넣거나, 분리 배포에서는 RAG가 소유하도록 정책 결정이 필요(§6 질문 2).

---

## 5. 구현 계획 (코드)

1. **신규 라우트 믹스인** `rag_history_routes.py` (`RagHistoryRoutesMixin`) — `rag_routes.py`와 같은 패턴, `/api/data_management/*` 디스패처. `rag_server.RagHandler`에 믹스인 추가(베이스 클래스 한 줄).
2. **변환기** `conversation_serializer.py` — `rag_queries` row → Chat dict, `conversations` row → Conversation dict, snippet 생성. 순수 함수(테스트 가능).
3. **마이그레이션 011**(§4) + `rag_db.ensure_rag_schema`에 projects 생성 best-effort.
4. **테스트** — 직렬화 순수함수 단위테스트(DB 불필요) + 엔드포인트 라우팅 테스트.
5. 라우트 디스패치는 `_handle_rag_route`처럼 `/api/data_management/`로 분기하는 `_handle_dm_route` 추가.

예상 규모: 라우트 믹스인 1 + 직렬화 1 + 마이그레이션 1쌍 + 테스트 1~2. 기존 `/api/rag/*` 무변경.

---

## 6. 미결 질문 — 갱신 (2026-06-11)

| # | 질문 | 상태 |
|---|---|---|
| 1 | 인증 방식 | **해소** → [COMPAT-run-graph.md](COMPAT-run-graph.md) §6. 권장: 신뢰헤더+공유시크릿(서버 대 서버) / 어댑터로 Bearer도 수용. 확인은 브라우저 Network 탭. |
| 2 | `conversations` 소유권(ALTER 위치) | 미해소 — 분리 배포에서 호스트 소유 테이블 ALTER 정책 결정 필요. |
| 3 | projects 사용 여부 | **보류 결정** → 본 문서 §3.6~3.9(프로젝트 엔드포인트)는 **이번 구현에서 제외**. `project_strid`는 항상 null로 처리, 컬럼만 예약. |
| 4 | 생성/스트리밍 엔드포인트 | **해소** → 그게 `Run_Graph_Conversation` PDF였음. [COMPAT-run-graph.md](COMPAT-run-graph.md)로 별도 정의. |
| 5 | `display_type=DOCUMENT_CHAT` | 미해소 — 현재 우리는 SEARCH형만. 문서 기반 대화 지원 여부 확인 필요. |

**이번 구현 범위(프로젝트 보류 반영)**: 대화 목록(3.1)·검색(3.2)·상세(3.3)·수정(3.4)·삭제(3.5)만. 프로젝트 4종은 스키마 컬럼(`project_strid`)만 예약하고 엔드포인트는 501 응답.

## 7. 구현 완료 (2026-06-11)

| 구성요소 | 파일 | 비고 |
|---|---|---|
| 마이그레이션 | `migrations/011_conversation_compat.sql`(+sqlite) | conversations 보강 컬럼 + 인덱스. **신규 DB는 `--apply`, 기존 DB는 `--sync`로 적용** |
| 직렬화 | `conversation_serializer.py` | Conversation/Chat/SearchResult/snippet — 순수 함수 |
| 라우트 | `rag_history_routes.py` (`HistoryRoutesMixin`) | 대화 5종 + projects 501. user_id 스코프, 소프트 삭제 |
| 배선 | `rag_server.py` | `/api/data_management/` 디스패치 + `do_PATCH` |
| 테스트 | `tests/test_conversation_serializer.py`(CI) + SQLite 엔드투엔드 스모크(목록·검색·상세·권한404·수정·소프트삭제) 통과 | |
