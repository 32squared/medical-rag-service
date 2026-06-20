# 04. RAG 생성 파이프라인

질의를 받아 검색→LLM 생성→가드레일→개인화 결합까지 수행하고 SSE로 스트리밍하는 본체.

- 코드: [`rag_engine.py`](../../rag_engine.py) `generate_response`
- 라우트: [`rag_routes.py`](../../rag_routes.py) `POST /api/rag/chat`
- 테스트: `tests/test_generate_response.py`, `tests/test_persona_e2e.py`

## 시그니처

```python
generate_response(
    query, conversation_id,
    provider_id=None, top_k=5,
    enable_guardrails=True,
    personal_findings=None,    # 개인화 findings(02 참고) — 있으면 답변에 블록 후append
) -> Iterator[dict]            # SSE 이벤트 제너레이터
```

## 이벤트 종류(SSE)

| type | 의미 |
|---|---|
| INFO | 상태(`status:started`) / 검색결과(`search_results`) |
| EVIDENCE_CHECK | 근거 게이트 결과(quality·decision·관련청크 수) — LLM 호출 전 |
| GENERATION | 답변 토큰(증분) |
| STOP | 종료 묶음(text·rag_query_id·citations·latency_ms·tokens·guardrail_action·evidence_quality·gate_decision) |
| ERROR | 오류(뒤에 STOP 따라옴) |

## 파이프라인 단계

```
1. INFO(started)
2. 응급 상태 체크 ─ 직전 턴이 EMERGENCY면 고정 응급응답 → STOP(emergency_redirect)
3. PII 마스킹 + 규칙기반 분류(classify_rule_based: intent·risk·domains)
4. 멀티턴 후속질의 재작성(검색질의만; 안전분류는 원질의 기준)
5. analytics_events: query_received (진입 이벤트)
6. 트리아지 ─ 비의료/모호 입력이면 되묻기 → STOP(triage_clarify)
7. 하이브리드 검색(hybrid_search) → INFO(search_results)
8. 근거 게이트(evaluate_retrieval_gate) → EVIDENCE_CHECK
     · INSUFFICIENT(enforce) → 템플릿 응답 → STOP(insufficient_evidence)
9. LLM 스트리밍(provider.stream_chat) → GENERATION*
10. 가드레일(ComplianceAnalyzer) → 인용 검증 → [개인화 블록 후append] → 면책/상단 고지
11. rag_queries 기록 + 감사필드 + 검수큐 + 멀티턴 컨텍스트 갱신
12. analytics_events: answer_shown
13. STOP(answer)
```

## 4종 종료 경로

| guardrail_action | 경로 | rag_query_id | 개인화 |
|---|---|---|---|
| `emergency_redirect` | 응급 — 고정 안내 | None | 억제(I7) |
| `triage_clarify` | 비의료/모호 — 되묻기 | None | 억제 |
| `insufficient_evidence` | 근거부족 — 길안내 | None | 억제 |
| `pass`/`regenerated`/`blocked`/`missing_structure` | 정상 답변 | 발급 | 결합(02) |

## 근거 게이트(Retrieval Gate)

검색 결과 품질을 LLM 호출 *전에* 판정한다.
- decision: `PASS` / `WEAK_PASS` / `INSUFFICIENT`
- INSUFFICIENT + enforce 모드 → LLM 스킵, "근거부족→길안내" 템플릿(거절수요 신호, E4).
- shadow 모드 → 로그만 남기고 정상 진행.

## 가드레일

`ComplianceAnalyzer`가 생성문을 분석해 위반 처리:
- CRITICAL → 안전 메시지로 **교체**(`blocked`)
- HIGH → fallback provider로 **재생성**(`regenerated`)
- 인용 검증: 범위 벗어난 `[N]` 제거, 인용 0건 → 재생성 시도
- 면책조항/상단 고지(119·응급실 문구) 자동 부착

## 개인화 주입(요약)

- 개인 데이터는 **LLM 프롬프트에 미투입**.
- 생성 후 `not emergency_detected`일 때만 `personal_context.safe_block(personal_findings, query)`를 후append.
- 상세: [02. 개인화 주입과 안전 경계](02-개인화-주입과-안전경계.md).

## 드레인 모드(끊김 복구)

클라이언트가 끊겨도 생성은 끝까지 완주하고 결과를 저장한다.
프론트는 `GET /api/rag/result?conversation_id=...`로 폴링해 복구한다.
