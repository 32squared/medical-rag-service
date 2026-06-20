# 기능별 매뉴얼 — 나만의 주치의 (medical-rag-service)

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

개인 데이터는 LLM 프롬프트에 **들어가지 않는다**. 결정적으로 해석한 중립 블록을 생성 *후* 답변에 덧붙인다.

## 매뉴얼 목차

| # | 문서 | 다루는 기능 |
|---|---|---|
| 01 | [개인화 해석 엔진](01-개인화-해석엔진.md) | `vital_rules`(밴드·추세·교차신호)·`env_rules`(환경)·안전 불변식 |
| 02 | [개인화 주입과 안전 경계](02-개인화-주입과-안전경계.md) | `personal_context`·`personalization_safety`·관련성 게이트·응급 억제 |
| 03 | [페르소나 테스트 서버](03-페르소나-테스트-서버.md) | `persona_test_server`·`test_personas/personas.json`(24종) |
| 04 | [RAG 생성 파이프라인](04-RAG-생성-파이프라인.md) | `rag_engine.generate_response`·4종 종료 경로·게이트·가드레일 |
| 05 | [이벤트 스토어 / 개선 루프](05-이벤트-스토어와-개선루프.md) | `analytics_events`·비식별 이벤트·E1~E7·골든셋 게이트 |
| 06 | [명시 피드백](06-명시-피드백.md) | `response_feedback`·`POST /api/rag/feedback` |
| 07 | (예정) wraith 호환 / 대화관리 API | `service_routes`·`rag_history_routes` |

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
