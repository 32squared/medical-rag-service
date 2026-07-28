# 생성/스트리밍 API — wraith Lab `Run Graph Conversation` 호환 정의서

> 원본: `Run_Graph_Conversation_20260508.pdf` (`POST /api/service/conversations/{graph_type}`, SSE).
> 목적: 이 **생성 엔드포인트**를 우리 `medical-rag-service`로 드롭인 교체하기 위한 호환 스펙 + 우리 파이프라인 매핑.
> 짝 문서: 이력관리 = [COMPAT-conversations.md](COMPAT-conversations.md), 우리 현행 = [INTERFACE.md](INTERFACE.md).
> 작성: 2026-06-11.

---

## 0. 이게 바로 "생성 엔드포인트"다

[COMPAT-conversations.md](COMPAT-conversations.md) §6에서 물었던 "생성/스트리밍 엔드포인트"가 **이 PDF**다.
정리하면 현행 RAG는 두 API 그룹으로 나뉜다:

| 그룹 | 엔드포인트 | 역할 | 우리 대응 |
|---|---|---|---|
| 생성/실행 | `POST /api/service/conversations/{graph_type}` | 질문 → 답변 SSE 스트리밍 | `POST /api/rag/chat` → **이 시그니처로 어댑트** |
| 이력 관리 | `/api/data_management/conversations`·`/projects` | 목록·검색·상세·수정·삭제 | 신규 호환 라우트(프로젝트는 보류) |

→ 드롭인 교체의 핵심은 **이 엔드포인트를 같은 경로·같은 요청 바디·같은 SSE 이벤트로 우리가 응답**하는 것.

---

## 1. 엔드포인트

`POST /api/service/conversations/{graph_type}` — SSE 스트리밍.

- `graph_type` ∈ `SUPERVISED_HYBRID_SEARCH` | `ORCHESTRATED_HYBRID_SEARCH` (경로 파라미터)
  - 우리 매핑: 둘 다 동일 파이프라인으로 처리(현재 우리는 단일 파이프라인). 값은 받되 동작 분기는 향후 옵션.

### 요청 바디
```json
{
  "query": "요즘 너무 피곤하고 어지러워요",
  "conversation_strid": null,
  "project_strid": null,
  "source_types": ["WEB"],
  "agent_strid": "SKIX_A1",
  "agent_input_field_to_value": {
    "Vital Signs": "[{\"bpm\":72,\"spo2\":98,\"bpd\":120,\"bps\":80,\"fever\":36.5,\"stress\":3,\"create_date\":\"2026-03-11 14:59:00\"}]",
    "Air Quality Score": "",
    "PHR": ""
  }
}
```

| 필드 | 타입 | 필수 | 설명 | 우리 매핑 |
|---|---|---|---|---|
| `query` | string | ✅ | 사용자 질의 | `generate_response(query=...)` 그대로 |
| `conversation_strid` | UUID\|null | ✅ | 기존 대화 이어가기, null=신규 | `conversation_id` (null이면 UUID 생성) |
| `project_strid` | UUID\|null | ✕ | 프로젝트 | **보류** — 받되 무시(null) |
| `source_types` | array(`WEB`\|`PUBMED`) | ✅ | 사용할 출처 | ⚠️ 우리는 국내 KB 기반 → §4 매핑 |
| `agent_strid` | string | ✕ | 에이전트 id (`SKIX_A1`) | 받되 현재 단일 동작 |
| `agent_input_field_to_value` | object | 조건부 | **Vital Signs / Air Quality Score / PHR** | ⭐ 개인화 입력 — §5 |

**Vital Signs** = JSON 배열을 문자열화: `bpm`(심박), `spo2`(산소포화도), `bps`/`bpd`(수축기/이완기 혈압), `fever`(체온), `stress`(스트레스), `create_date`.

---

## 2. SSE 이벤트 — 원본 vs 우리

각 줄 `data: <JSON>\n\n`. 정상 흐름: `INFO(연결) → PROGRESS* → INFO(search_results) → GENERATION* → INFO(follow_ups/token_usage) → STOP`.

| 원본 type | 페이로드 | 우리 현재(`/api/rag/chat`) | 어댑트 방법 |
|---|---|---|---|
| `INFO` (연결) | `{data:{graph_usage_strid, conversation_strid}}` | `INFO {data:{status:"started",query}}` | **신규** — 시작 시 `conversation_strid`+생성 usid 발급해 emit |
| `PROGRESS` | `{strid,status,level,display_message,metadata{label,source_type},result_items}` | (없음) | **신규(선택)** — 검색/추론 단계 표시. 최소구현: 검색 시작/완료 2건 emit |
| `INFO` (search_results) | `{data:{search_results:[SearchResult]}}` | `INFO {data:{search_results:[...]}}` | 필드 형태 변환(§3) |
| `EVIDENCE_CHECK` | (원본에 없음) | `{data:{quality,decision,...}}` | 원본 호환 위해 **숨김 또는 PROGRESS로 래핑** |
| `GENERATION` | `{type,text}` 토큰 조각, 인용 `[2:1]` 형식 | `{type,text}` | ✅ 거의 동일. 인용 마커 형식만 조정(§3.2) |
| `INFO` (follow_ups) | `{data:{follow_ups_started}}` / `{data:{follow_ups:[{query,agent_strid}]}}` | (없음) | **신규(선택)** — 후속질문 제안. 우리 `_should_clarify`/체크리스트 활용 |
| `INFO` (token_usage) | `{data:{token_usage:{model:{input,output,total}}}}` | STOP.tokens | INFO로 재배치 |
| `STOP` | `{type:"STOP"}` (필드 없음) | `{type:"STOP",text,citations,...}` | ⚠️ 원본 STOP은 **빈 신호**. 우리 STOP의 부가정보는 INFO로 옮기고 STOP은 종료 신호만 |
| `ERROR` | `{type,message}` (뒤에 STOP) | `{type,message}` | ✅ 동일 + STOP 후행 |
| `KEEP_ALIVE` | `{}` | `{type:"KEEP_ALIVE"}` | ✅ 동일 |

> **핵심 차이**: 원본은 답변 본문·인용을 **GENERATION 스트림과 search_results(INFO)**로 전달하고 `STOP`은 종료 신호만. 우리는 STOP에 최종 묶음을 싣는다. → 어댑터에서 **STOP 직전에 token_usage(INFO) emit + STOP은 빈 신호**로 맞춘다.

---

## 3. SearchResult 매핑

### 3.1 구조 차이
원본 SearchResult는 **학술 논문/웹**(PubMed·Web) 중심: `strid, source_type(PUBMED|WEB), content_type(ARTICLE|WEBPAGE), title, date, relevant_chunks[], cached_result_strid` + ARTICLE는 `doi,url,abstract,authors,author_affiliations,source,year,sjr_quartile,pdf_url,citation_count,figure_urls` / WEBPAGE는 `url,snippet,source,pdf_urls,display_link,favicon`.

우리 청크는 **국내 KB**(KDCA/DUR/지침 등): `chunk_id, document_id, content, source_id, title, source_url, evidence_level, evidence_topic, score`.

**매핑(우리 → 원본 SearchResult)**:
```
strid          ← chunk_id (또는 document_id)
source_type    ← "WEB" 로 고정(또는 source_id 기반 커스텀; PUBMED 아님)
content_type   ← "WEBPAGE"
title          ← title
url            ← source_url
snippet        ← content[:200]
source         ← source_id 표시명(예: "질병관리청 국가건강정보포털")
relevant_chunks← [{strid: chunk_id, type:"md", chunk_index:0, chunk_text: content, start_offset:-1, end_offset:-1}]
date           ← (KB는 발행일 색인 후) published_at | null
```
> ARTICLE 전용 필드(doi/authors/sjr_quartile 등)는 KB엔 없으므로 WEBPAGE 형태로 통일. 프론트가 ARTICLE 카드만 렌더하면 협의 필요(§6 Q).

### 3.2 인용 마커
원본 GENERATION 본문은 `[2:1][3:1]`(출처index:청크index) 형식. 우리 현재는 `[1]`(단일 번호). → 어댑터에서 우리 citations를 `[n:0]` 형태로 변환하거나, 프론트가 `[n]`도 허용하는지 확인(§6 Q).

---

## 4. `source_types`(WEB/PUBMED) 처리

원본은 라이브 웹/PubMed 검색 에이전트. 우리는 **큐레이션된 국내 KB 검색**이라 의미가 다르다.

- **MVP**: `source_types`를 받되 무시하고 우리 KB로 검색(가장 빠른 드롭인). 답변 품질은 국내 의료법·인용 보장 측면에서 오히려 강점.
- **확장**: `PUBMED`/`WEB` 요청 시 별도 커넥터로 라이브 검색 추가(로드맵 — 글로벌 단계).

> 영업적 메시지: "라이브 웹 검색"을 "검증된 국내 권위 출처 + 인용 보장"으로 바꾸는 것이 우리의 차별화이자 의료법 안전점.

---

## 5. ⭐ Vital Signs / PHR / Air Quality — 개인화 입력 (전략적 핵심)

원본이 이미 `agent_input_field_to_value`로 **생체신호·PHR·공기질을 입력 계약으로 정의**해 두었다. 이는 우리 마스터플랜([../plan/00-vision-master-plan.md](../plan/00-vision-master-plan.md))의 개인화 비전과 **그대로 호환**된다.

| 단계 | 동작 |
|---|---|
| **MVP(드롭인)** | 필드를 받아 파싱·검증만 하고 답변엔 미반영(계약 호환 유지). 수신 자체를 감사 로그에 기록. |
| **Phase 1** | Vital Signs를 **규칙 엔진**(`vital_rules`)에 넣어 참조범위 대조 findings 생성 → Evidence Pack에 `[R#]`로 주입(원시값은 LLM에 직접 안 보냄 — 안전 설계 P1). |
| **Phase 1** | Air Quality → `context_feeds`(이미 구현된 CAI 등급 판정)와 결합. PHR → 복용약 × DUR 교차. |

> 즉 이 엔드포인트를 호환 구현하는 것만으로 **개인화 입력 파이프가 자동으로 열린다.** 마스터플랜 Phase 1을 이 계약 위에서 진행하면 된다.

---

## 6. 인증 — 권장안 (질문 1 답변)

세 가지 방식이 있고, **무엇이 적합한지는 "앱과 RAG 사이에 백엔드(게이트웨이)가 있는가"로 갈린다.**

| 방식 | 동작 | 적합한 상황 |
|---|---|---|
| **신뢰헤더 + 공유시크릿** (우리 현행) | 앱 백엔드가 사용자 인증 후 `X-User-Id` + `X-Rag-Trust`(공유 비밀)로 RAG 호출 | **앱↔RAG가 서버 대 서버**(대부분의 프로덕션). 추가 인증 코드 0 |
| **Bearer 토큰(JWT)** | 클라이언트가 `Authorization: Bearer <JWT>` 전송, RAG가 검증 | 브라우저가 RAG를 **직접** 호출하는 구조 |
| **쿠키 세션** | 브라우저 쿠키 → 서버 세션 검증 | 레거시 동일 도메인 세션 |

**권장**: 대부분의 앱은 *브라우저 → 앱 백엔드 → RAG* 구조라서, **신뢰헤더 + 공유시크릿(우리가 이미 가진 `RAG_TRUST_SECRET`)이 가장 적합하고 추가 작업이 없다.** "Bearer 토큰"은 브라우저가 RAG를 직접 부를 때만 필요하다.

**확인 방법**(브라우저 개발자도구 → Network 탭에서 현재 앱이 RAG 호출 시 Request Headers 확인):
- `Authorization: Bearer ...`가 보이면 → Bearer 방식이므로 RAG가 JWT 검증해야 함.
- `Cookie: ...`만 보이고 별도 백엔드가 중계하면 → 신뢰헤더 방식이 맞음.

**안전 설계**: 우리 서버를 **둘 다 수용**하게 만들면 위험이 없다 — `Authorization: Bearer`가 오면 그걸로 user 추출, 없으면 `X-User-Id`(신뢰헤더) 사용. 어댑터 한 겹이면 끝. (구현 시 그렇게 만들 예정)

---

## 7. 구현 계획 (additive, 기존 `/api/rag/*` 무변경)

1. **어댑터 라우트** `service_routes.py` (`ServiceRoutesMixin`): `POST /api/service/conversations/{graph_type}` 수신 → 바디 파싱 → `generate_response(...)` 호출 → **이벤트 변환기**로 원본 SSE 형식으로 재방출.
2. **이벤트 변환기** `wraith_sse_adapter.py` (순수 함수): 우리 이벤트(INFO/EVIDENCE_CHECK/GENERATION/STOP) → 원본 이벤트(INFO연결/PROGRESS/search_results/GENERATION/token_usage/STOP). search_result 필드 매핑(§3) 포함. **DB 없이 단위테스트 가능.**
3. **인증 어댑터** `auth_resolver.py`: `Authorization: Bearer` 우선, 없으면 신뢰헤더. user_id 추출 일원화.
4. **Vital Signs 파서** `vital_input.py`: `agent_input_field_to_value`의 Vital Signs JSON 파싱·검증(현재는 로깅, Phase 1에 규칙엔진 연결).
5. **테스트**: SSE 변환·바디 파싱·vital 파서 단위테스트 + 골든 시나리오에 생체신호 케이스.

예상 규모: 라우트 1 + 변환기 1 + 인증 1 + vital 파서 1 + 테스트. 기존 파이프라인 재사용.

---

## 8. 남은 확인 사항 (프론트 호환 정밀도)
1. 프론트가 **인용 마커**를 `[n:m]`만 받는지, `[n]`도 허용하는지.
2. 프론트가 **ARTICLE 카드 전용 필드**(authors/doi/sjr_quartile)를 요구하는지 — 요구하면 KB→ARTICLE 매핑에 빈값 채움 필요.
3. **PROGRESS / follow_ups** 이벤트를 프론트가 필수로 소비하는지(아니면 INFO/GENERATION/STOP만으로 동작하는지) — 필수 아니면 MVP에서 생략 가능.
4. `graph_type` 두 값의 동작 차이를 우리가 구분해야 하는지.

> 1·3이 "관대"하면 MVP 드롭인이 매우 빠르다(핵심 INFO/GENERATION/STOP만 정확히 맞추면 됨).
