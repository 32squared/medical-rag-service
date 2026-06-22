# 기능별 매뉴얼 — 마이헬스케어 (medical-rag-service)

> ⚠️ **현재 단계: 출시 전 검토용 프로토타입** (점진적 완성 중). 테스트 그린 ≠ 출시 가능.
> **출시 전 반드시 끝내야 할 업무(법무·동의·의료 콘텐츠 등)는 [LAUNCH-READINESS.md](../LAUNCH-READINESS.md)** 참조 —
> 특히 A(의료법 검토)·B(동의 시스템)·D(KB 의료 검수)는 출시 차단(🔴) 항목.

> 의료법(무면허 의료행위) 경계 안에서 개인 데이터를 활용하는 한국어 의료정보 RAG.
> 핵심 원칙: **원시 측정값은 LLM에 미투입**, 개인화는 결정적 엔진이 해석해 **중립 라벨/노트**로만
> 답변에 결합한다. 진단·처방 단정 0.

## 시스템 한눈에

```
사용자 질의 + 개인화 입력(agent_input_field_to_value)
        │
        ▼
[경계선 ②] vital_rules / env_rules  ── 결정적 해석 → findings(라벨·노트만, 원시값 0)
        │
        ▼
[경계선 ③] personal_context.safe_block  ── 관련성 게이트 + 안전 백스톱 → 주입 블록
        │
        ▼
rag_engine.generate_response  ── 검색→LLM 생성→가드레일→ (개인화 블록 후append) → SSE
        │
        ├─▶ analytics_events  ── 비식별 이벤트(개선 루프 E2)
        └─▶ response_feedback ── 👍/👎 명시 피드백
```

**원시 측정값은 LLM에 절대 안 들어간다.** 개인화 결합은 2경로: ① (기본) 결정적 중립 블록을 생성 *후* 답변에 후append, ② (방향2·옵트인) **비식별 밴드 라벨만**(원시값·진단명 아님) LLM system_prompt에 주입(6게이트 fail-closed, 기본 off).

> **전체를 한 문서로 보려면 → [00 전체 기능·개발 매뉴얼](00-전체-기능-매뉴얼.md)** (2026-06-22 최신, 성능·방향2·관찰성·운영 포함).
> **인쇄용 PDF(다이어그램 5종 포함) → [마이헬스케어-기능매뉴얼.pdf](마이헬스케어-기능매뉴얼.pdf)** · 재생성: `python docs/manual/build/build_manual_pdf.py` → Chrome `--headless --print-to-pdf`.
> **임원·비개발자용 쉬운 안내서(용어 없음) → [임원용-쉬운설명.md](임원용-쉬운설명.md) · [마이헬스케어-쉬운안내서.pdf](마이헬스케어-쉬운안내서.pdf)** (4쪽, 신호등·안전장치 그림). 재생성: `python docs/manual/build/build_exec_pdf.py`.

## 매뉴얼 목차

| # | 문서 | 다루는 기능 |
|---|---|---|
| **00** | [**전체 기능·개발 매뉴얼**](00-전체-기능-매뉴얼.md) | **종합 — 아키텍처·전 기능·성능·운영·블로커** |
| 01 | [개인화 해석 엔진](01-개인화-해석엔진.md) | `vital_rules`(밴드·추세·교차신호)·`env_rules`(환경)·안전 불변식 |
| 02 | [개인화 주입과 안전 경계](02-개인화-주입과-안전경계.md) | `personal_context`·`personalization_safety`·관련성 게이트·응급 억제 |
| 03 | [페르소나 테스트 서버](03-페르소나-테스트-서버.md) | `persona_test_server`·`test_personas/personas.json`(24종) |
| 04 | [RAG 생성 파이프라인](04-RAG-생성-파이프라인.md) | `rag_engine.generate_response`·4종 종료 경로·게이트·가드레일 |
| 05 | [이벤트 스토어 / 개선 루프](05-이벤트-스토어와-개선루프.md) | `analytics_events`·비식별 이벤트·E1~E7·골든셋 게이트 |
| 06 | [명시 피드백](06-명시-피드백.md) | `response_feedback`·`POST /api/rag/feedback` |
| 07 | [wraith 호환 / 대화관리 API](07-wraith호환-대화관리-API.md) | `service_routes`·`wraith_sse_adapter`·`rag_history_routes` |

## 안전 불변식 요약 (전 기능 공통)

| ID | 규칙 |
|---|---|
| I1 | 원시 측정값(120/80 등)을 반환·표면화하지 않는다. 밴드 라벨·노트만. |
| I7 | 응급 감지 시 개인화 결합을 억제한다(응급 안내 우선). |
| I8 | 임상 판독 금지 신호(ECG·웰니스 등급)는 밴드 조회 자체를 안 함(denied). |
| I12 | 사용자 라벨은 중립 3단(안정/주의/경고)만. 질환 라벨은 내부 감사용. |
| 게이트 | 질의 scope와 무관한 finding은 표면화하지 않는다(과노출 차단). |
| E2 | 분석 이벤트는 비식별(라벨·카운트·불리언)만. 질의원문·원시값·진단명·PII 금지. |

## 빠른 시작

```bash
# 페르소나를 골라 개인화 대화 미리보기(백엔드 불필요)
python persona_test_server.py
# → http://localhost:8770

# 전체 테스트
python -m pytest tests/ -q
```

## 부록 A — 마이그레이션 (PG / `_sqlite`)

| # | 테이블·변경 | 매뉴얼 |
|---|---|---|
| 001 | kb_sources·kb_documents·kb_chunks·llm_providers·**rag_queries** | 04 |
| 005 | evidence_grounding(근거 게이트 컬럼) | 04 |
| 010 | vital_reference_ranges | 01 |
| 011 | conversations 호환 컬럼 | 07 |
| 013 | rag_queries 멀티턴 감사 컬럼 | 04 |
| 014 | rag_projects | 07 |
| 015 | **analytics_events**(비식별 이벤트 스토어) | 05 |
| 016 | **response_feedback**(명시 피드백) | 06 |

> SQLite 마이그레이션은 러너가 세미콜론 단위로 split — **주석에 세미콜론 금지**.
> 영속 개인화(personal_record 등)는 017+로 예약(현재 in-memory 시드).

## 부록 B — 핵심 모듈 맵

| 모듈 | 역할 | 매뉴얼 |
|---|---|---|
| `vital_rules` / `env_rules` | 개인화 해석(밴드·추세·교차·환경) | 01 |
| `personal_context` / `personalization_safety` | 주입 블록 + 안전 백스톱 | 02 |
| `vital_input` | agent_input 파싱 | 01·07 |
| `rag_engine` | 생성 파이프라인 | 04 |
| `analytics_events` | 비식별 이벤트 | 05 |
| `rag_db` / `rag_routes` | 피드백·라우트 | 06 |
| `service_routes` / `wraith_sse_adapter` / `rag_history_routes` | wraith 호환 | 07 |
| `persona_test_server` | 페르소나 테스트 | 03 |
