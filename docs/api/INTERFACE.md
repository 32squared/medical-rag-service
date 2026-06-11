# Medical RAG — 외부 인터페이스 정의서 (API Spec)

> 대상: `rag_server.py`(RAG 독립 HTTP 서비스)를 외부에서 호출하기 위한 계약서.
> 기준 코드: `rag_server.py`, `rag_routes.py`, `rag_engine.generate_response`.
> 버전: 2026-06-11 기준 현행 동작.

---

## 1. 개요

- **프로토콜**: HTTP/1.1. 채팅 응답은 **SSE(Server-Sent Events)** 스트리밍.
- **경로 접두어**: 모든 기능 엔드포인트는 `/api/rag/*`. 그 외는 헬스체크.
- **문자셋**: 요청/응답 모두 UTF-8(JSON `ensure_ascii=false`).
- **CORS**: 모든 응답에 허용 헤더 포함(`Access-Control-Allow-Origin: *`). `OPTIONS` 프리플라이트 204 응답.
- **인증 모델**: 쿠키/세션이 아니라 **신뢰 헤더(trust header)**. 원래 호스트(리버스 프록시)가 세션을 검증한 뒤 헤더로 변환해 전달하는 전제. 직접 호출 시에는 이 헤더들을 직접 채워 보낸다(§3).

---

## 2. 베이스 주소 (Base URL)

| 환경 | 주소 | 비고 |
|---|---|---|
| 로컬 | `http://localhost:8080` | `python rag_server.py --port 8080` (또는 `PORT` 환경변수) |
| **Cloud Run(DEV)** | **`https://medical-rag-dev-cbtevhmzrq-du.a.run.app`** | 2026-06-11 배포·검증 완료. 비공개(`--no-allow-unauthenticated`) — Google ID 토큰 필요(아래) |
| Cloud Run(운영) | `https://<cloud-run-host>` | `deploy-rag.ps1 -Prod`의 `medical-rag` 서비스 (미배포) |

> Cloud Run은 고정 IP가 아닌 HTTPS URL로 접근한다. DEV는 IAM 비공개 서비스라
> 요청에 `Authorization: Bearer $(gcloud auth print-identity-token)` (Google ID 토큰)이 필요하며,
> 호출 계정에 `roles/run.invoker` 권한이 있어야 한다. 앱 레벨 사용자 식별은 별도로 `X-User-Id` 헤더 사용.
> 외부 팀 계정 허용: `gcloud run services add-iam-policy-binding medical-rag-dev --region asia-northeast3 --member=user:<email> --role=roles/run.invoker`

> 본 문서의 예시는 `BASE=http://localhost:8080` 기준. 운영 호스트로 바꾸면 동일하게 동작.

---

## 3. 인증 헤더

| 헤더 | 필수 | 설명 |
|---|---|---|
| `X-User-Id` | ✅(테스터) | 사용자 식별자. 비어 있으면 비인증으로 간주(admin 헤더가 없는 한 403). |
| `X-User-Name` | 선택 | 표시용 이름. **URL 인코딩 필수**(한글 이름의 latin-1 헤더 인코딩 실패 회피). 예: `%EA%B9%80%EC%9D%98%EC%82%AC` |
| `X-User-Role` | 선택 | `tester`(기본) 또는 `admin`. `admin`이면 모든 권한 통과. |
| `X-User-Permissions` | 선택 | KB 관리 권한. CSV(`manage_kb,...`) 또는 JSON 배열(`["manage_kb"]`). `*`이면 전체 허용. |
| `X-Rag-Trust` | 조건부 | 서버에 `RAG_TRUST_SECRET`이 설정된 경우에만 필요. 이 값과 일치해야 모든 요청 통과(호스트만 호출하도록 제한). 미설정이면 불필요. |

- **최소 호출**: `X-User-Id: tester1` 한 개면 채팅·조회 가능.
- **KB 쓰기**(문서 생성/수정/삭제/승인/reembed): `X-User-Role: admin` **또는** `X-User-Permissions: manage_kb`.

---

## 4. 엔드포인트 목록

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/` `/health` `/healthz` | 불필요 | 헬스체크 |
| POST | `/api/rag/chat` | 테스터+ | **RAG 답변 생성 (SSE 스트리밍)** |
| GET | `/api/rag/result` | 테스터+ | SSE 끊김 복구용 결과 폴링 |
| GET | `/api/rag/kb/sources` | 테스터+ | KB 출처 목록 |
| GET | `/api/rag/kb/documents` | 테스터+ | KB 문서 목록(쿼리 필터) |
| GET | `/api/rag/kb/documents/{id}` | 테스터+ | KB 문서 단건 |
| POST | `/api/rag/kb/documents` | manage_kb | KB 문서 생성 |
| PUT | `/api/rag/kb/documents/{id}` | manage_kb | KB 문서 수정 |
| DELETE | `/api/rag/kb/documents/{id}` | manage_kb | KB 문서 삭제 |
| POST | `/api/rag/kb/documents/{id}/reembed` | manage_kb | 문서 재임베딩 |
| POST | `/api/rag/kb/approve` | manage_kb | 문서 승인 |
| POST | `/api/rag/kb/reject` | manage_kb | 문서 반려 |

> **전제 조건**: 채팅·결과·KB 기능은 (1) 서버 환경변수 `RAG_ENABLED=true`, (2) `DATABASE_URL`이 **PostgreSQL+pgvector**를 가리켜야 동작. SQLite 모드에서는 채팅이 `503 RAG_REQUIRES_POSTGRES`를 반환한다.

---

## 5. POST `/api/rag/chat` — 답변 생성 (SSE)

### 요청
- 헤더: `Content-Type: application/json` + 인증 헤더(§3)
- 본문:

```json
{
  "query": "발열이 나는데 어떻게 해야 하나요?",
  "conversation_id": "conv-123",
  "provider_id": null,
  "top_k": 5,
  "enable_guardrails": true
}
```

| 필드 | 타입 | 필수 | 기본 | 설명 |
|---|---|---|---|---|
| `query` | string | ✅ | — | 사용자 질의 |
| `conversation_id` | string | ✕ | UUID 자동생성 | 대화 식별자. 폴링 복구·이력에 사용 |
| `provider_id` | string\|null | ✕ | 환경변수 기본(`openai_gpt5`) | LLM 프로바이더 id |
| `top_k` | int | ✕ | 5 | 검색 청크 수 |
| `enable_guardrails` | bool | ✕ | true | 가드레일/재생성 활성화 |

### 응답 — `Content-Type: text/event-stream`
각 줄은 `data: <JSON>\n\n`. 이벤트 순서(정상): **INFO(시작) → INFO(검색결과) → EVIDENCE_CHECK → GENERATION*(다수) → STOP**. 안전 분기 시 GENERATION→STOP만 올 수 있음.

| `type` | 페이로드 | 의미 |
|---|---|---|
| `INFO` | `{data:{status:"started", query}}` 또는 `{data:{search_results:[...]}}` | 시작 알림 / 검색 청크 미리보기 |
| `EVIDENCE_CHECK` | `{data:{quality, decision, top1_score, chunk_count, relevant_count, topic_match, evidence_levels, reasons}}` | 근거 충분성 게이트 결과. `quality`∈`high|medium|low|insufficient`, `decision`∈`PASS|WEAK_PASS|INSUFFICIENT` |
| `GENERATION` | `{text:"부분 답변"}` | 토큰 스트림 조각(누적 표시) |
| `KEEP_ALIVE` | `{}` | 장시간 생성 중 연결 유지용(무시) |
| `STOP` | (아래) | 최종 이벤트 |
| `ERROR` | `{message:"..."}` | 오류 |

**STOP 페이로드:**
```json
{
  "type": "STOP",
  "text": "완성된 전체 답변 …[1] …[2]",
  "rag_query_id": "rq_abc123",
  "citations": [
    {"marker":"[1]","chunk_id":"...","source_id":"health_kdca","title":"…","source_url":"https://…"}
  ],
  "latency_ms": 4210,
  "tokens": {"input": 1200, "output": 350},
  "guardrail_action": "pass",
  "evidence_quality": "high",
  "gate_decision": "PASS"
}
```
- `search_results[]` 항목 필드: `chunk_id, document_id, content(미리보기 300자), section_path, source_id, title, source_url, evidence_level, evidence_topic, severity, score, boost_reasons, cosine_score, topic_alignment_score`.
- `guardrail_action`∈`pass | regenerated | blocked`.

### 오류 응답(스트림 시작 전, JSON)
| 코드 | 본문 | 원인 |
|---|---|---|
| 400 | `{"error":"query is required"}` | query 누락/공백 |
| 403 | `{"error":"인증이 필요합니다 (신뢰헤더 누락)"}` | 인증 헤더 없음 |
| 503 | `{"error":"…","code":"RAG_DISABLED"}` | `RAG_ENABLED=false` |
| 503 | `{"error":"…","code":"RAG_REQUIRES_POSTGRES"}` | SQLite 모드 |

---

## 6. GET `/api/rag/result` — 끊김 복구 폴링

SSE 연결이 끊겨도 서버는 생성을 끝까지 마쳐 `rag_queries`에 저장한다. 프론트는 이 엔드포인트를 폴링해 결과를 복구.

- 쿼리스트링: `conversation_id`(필수), `query`(선택, 일치 시 정확 매칭), `since_sec`(선택, 기본 300, 10~1800)
- 예: `GET /api/rag/result?conversation_id=conv-123&query=발열&since_sec=120`

```json
// 생성 중/없음
{"status": "pending"}
// 완료
{
  "status": "ready",
  "rag_query_id": "rq_abc123",
  "answer": "…",
  "citations": [ ... ],
  "guardrail_action": "pass",
  "evidence_quality": "high",
  "created_at": "2026-06-11T…"
}
```

---

## 7. KB 관리 API (요약)

### GET `/api/rag/kb/sources`
```json
{"sources":[{"id":"health_kdca","name":"…","source_type":"public","license":"kogl_type1","url":"…","update_frequency":"…","is_active":1,"created_at":"…"}]}
```

### GET `/api/rag/kb/documents?status=active&source_id=health_kdca&limit=50`
문서 목록(상태/출처 필터). 상세는 `GET /api/rag/kb/documents/{id}`.

### POST `/api/rag/kb/documents` (manage_kb)
```json
{
  "title": "발열 대처 안내",
  "content_md": "# 발열 …",
  "source_id": "internal_md",
  "status": "draft",
  "evidence_country": "KR",
  "evidence_topic": "fever",
  "regulatory_korea": false,
  "topic_keywords": ["발열","해열"],
  "metadata": {"evidence_level":"B"}
}
```
응답: `{"document_id":"…","chunks_count":N,"status":"draft"}`(생성 시 청킹+임베딩 수행).

### 기타
- `PUT /api/rag/kb/documents/{id}` — `title|content_md|status|evidence_level|metadata|source_id` 부분 수정.
- `DELETE /api/rag/kb/documents/{id}` — 삭제.
- `POST /api/rag/kb/documents/{id}/reembed` — 재임베딩.
- `POST /api/rag/kb/approve` / `reject` — body `{"document_id":"…","reason":"…"}`.

---

## 8. 서버 기동 (로컬 테스트)

```bash
# PostgreSQL + pgvector 가 있는 경우 (채팅 가능)
export DATABASE_URL="postgresql://app_user:PASS@localhost:5432/medical_app"
export RAG_ENABLED=true
export OPENAI_API_KEY="sk-..."        # 생성에 필요
# export RAG_TRUST_SECRET="..."       # 설정 시 X-Rag-Trust 헤더 필요
python rag_server.py --port 8080
```

| 환경변수 | 필수 | 설명 |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL 연결. 미설정 시 기동 거부(로컬은 `RAG_ALLOW_SQLITE=1`로 우회 가능하나 채팅 불가) |
| `RAG_ENABLED` | ✅ | `true`라야 `/api/rag/chat`·`result`·KB 동작 |
| `OPENAI_API_KEY` | ✅(생성) | LLM 호출 키 (`RAG_LLM_MODEL` 기본 `gpt-5.4-mini`) |
| `RAG_TRUST_SECRET` | 선택 | 설정 시 `X-Rag-Trust` 일치 강제 |
| `PORT` | 선택 | 기본 8080 |
| `RETRIEVAL_GATE_ENFORCE` | 선택 | `true`면 근거부족 시 LLM 스킵하고 템플릿 응답 |

> 헬스체크 `GET /health`는 DB/키 없이도 200(`{"status":"ok","service":"rag","schema":"…"}`)을 반환하므로 배선 점검용으로 먼저 사용.

---

## 9. 호출 예시

### curl — 헬스
```bash
curl http://localhost:8080/health
```

### curl — 채팅(SSE, 스트림 그대로 출력)
```bash
curl -N -X POST http://localhost:8080/api/rag/chat \
  -H "Content-Type: application/json" \
  -H "X-User-Id: tester1" \
  -H "X-User-Role: tester" \
  -d '{"query":"발열이 나는데 어떻게 하나요?","top_k":5}'
```

### curl — 결과 폴링
```bash
curl "http://localhost:8080/api/rag/result?conversation_id=conv-123&since_sec=120" \
  -H "X-User-Id: tester1"
```

### Python — SSE 파싱
```python
import json, requests

BASE = "http://localhost:8080"
headers = {"X-User-Id": "tester1", "Content-Type": "application/json"}
body = {"query": "발열이 나는데 어떻게 하나요?", "conversation_id": "conv-123", "top_k": 5}

with requests.post(f"{BASE}/api/rag/chat", headers=headers, json=body, stream=True) as r:
    answer = ""
    for raw in r.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data: "):
            continue
        ev = json.loads(raw[6:])
        t = ev.get("type")
        if t == "EVIDENCE_CHECK":
            print("근거:", ev["data"]["quality"], ev["data"]["decision"])
        elif t == "GENERATION":
            answer += ev.get("text", "")
        elif t == "STOP":
            print("\n=== 최종 ===")
            print(ev["text"])
            print("인용:", [c.get("source_url") for c in ev.get("citations", [])])
            print("근거품질:", ev.get("evidence_quality"), "| 가드레일:", ev.get("guardrail_action"))
        elif t == "ERROR":
            print("오류:", ev.get("message"))
```

### JavaScript(fetch + 수동 SSE 파싱)
```javascript
const res = await fetch(`${BASE}/api/rag/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-User-Id": "tester1" },
  body: JSON.stringify({ query: "발열이 나는데 어떻게 하나요?", top_k: 5 }),
});
const reader = res.body.getReader();
const dec = new TextDecoder();
let buf = "", answer = "";
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buf += dec.decode(value, { stream: true });
  const parts = buf.split("\n\n"); buf = parts.pop();
  for (const p of parts) {
    if (!p.startsWith("data: ")) continue;
    const ev = JSON.parse(p.slice(6));
    if (ev.type === "GENERATION") answer += ev.text;
    if (ev.type === "STOP") console.log("최종:", ev.text, ev.citations);
  }
}
```

---

## 10. 테스트 체크리스트

1. `GET /health` → 200 (배선 확인, DB/키 불필요)
2. `RAG_ENABLED`·`DATABASE_URL`(PG)·`OPENAI_API_KEY` 설정 후 기동
3. `POST /api/rag/chat`로 SSE 수신 — `EVIDENCE_CHECK`→`GENERATION`→`STOP` 흐름 확인
4. 응급 질의("가슴이 아프고 숨이 안 쉬어져요") → 119 안내 + 보수적 응답 확인
5. 끊김 시 `GET /api/rag/result`로 동일 답변 복구 확인
6. KB: `manage_kb` 헤더로 `POST /api/rag/kb/documents` → `GET /api/rag/kb/documents`에서 조회

> 참고 검증 스크립트: `tests/auto_validate_rag.py`(DEV URL + 토큰 기반 10시나리오 SSE 검증).
