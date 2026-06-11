# 멀티턴 문맥화 설계 (Sprint 3 착수 문서)

> 작성: 2026-06-11 · [05-execution-plan.md](05-execution-plan.md) Sprint 3 항목 7.
> 상태: **설계 문서** (구현 전). 현 시스템은 emergency_state만 대화 단위로 보존하고,
> 일반 멀티턴 문맥은 없다([00-vision-master-plan.md](00-vision-master-plan.md) 약점 진단).

---

## 1. 문제 정의

현재 각 질의는 독립 처리된다. 그래서 자연스러운 후속 대화가 깨진다:

```
U: 머리가 아파요
A: (두통 정보 + 신경과 안내)
U: 언제 병원 가야 해요?       ← "무엇에 대한" 병원인지 문맥 소실
U: 약은 먹어도 되나요?         ← "무슨 증상의" 약인지 소실
```

후속 질의("언제 병원 가야 해요")는 그 자체로는 증상 매칭·검색이 안 되어
insufficient로 빠지거나 엉뚱한 검색을 한다. 이미 만든 자산(증상 매칭·진료과·
레드플래그)이 첫 턴에만 작동하고 둘째 턴부터 끊긴다.

## 2. 설계 원칙 (마스터플랜 정합)

| 원칙 | 멀티턴 적용 |
|---|---|
| P1 안전 우선 분기 | 대화 이력과 무관하게 매 턴 crisis/emergency 재평가(이력으로 응급을 *해제*하지 않는다). 기존 emergency_state 머신과 일관 |
| 개인정보 최소화 | 이력 저장은 마스킹된 질의·증상키·intent 등 *비식별 요약*만. 원문 장기보관 지양 |
| 측정 우선 | 멀티턴 골든셋(대화 시퀀스) 추가 후에만 머지 |
| 결정적 우선, LLM은 보조 | 후속질의 재작성은 규칙(대명사·생략 복원) 우선, 모호하면 LLM 1콜 |

## 3. 아키텍처 — 세션 컨텍스트 + 질의 재작성

```
대화 턴 입력
   │
   ├─[1] 세션 컨텍스트 로드 (conversation_id 키)
   │       last_symptom_keys, last_intent, last_departments,
   │       turn_count, (emergency_state ← 기존)
   │
   ├─[2] 후속질의 판정 (is_followup)
   │       규칙: 증상 매칭 0건 + 지시/생략 신호("그거","언제","약은","얼마나")
   │       + turn_count>0
   │
   ├─[3] 질의 재작성 (standalone화)  ← 후속일 때만
   │       규칙 우선: last_symptom의 대표 표현을 주어로 복원
   │         "언제 병원 가야 해요" + last=두통
   │         → "두통일 때 언제 병원에 가야 하나요"
   │       모호하면 LLM 1콜(문맥+질의→standalone 질의)
   │
   ├─[4] 기존 파이프라인 (재작성된 질의로)
   │       PII→분류(매 턴 안전 재평가)→증상매칭→검색→생성→인용검증
   │
   └─[5] 세션 컨텍스트 갱신 (이번 턴 증상키/intent/진료과 저장)
```

## 4. 데이터 모델 (additive, 기존 rag_conversation_state 확장)

기존 `rag_conversation_state`(emergency_state 보유)에 컬럼 추가 — 멱등 마이그레이션:

```sql
-- migrations/011_conversation_context.sql (예정)
ALTER TABLE rag_conversation_state ADD COLUMN IF NOT EXISTS last_symptom_keys TEXT DEFAULT '[]';
ALTER TABLE rag_conversation_state ADD COLUMN IF NOT EXISTS last_intent       TEXT;
ALTER TABLE rag_conversation_state ADD COLUMN IF NOT EXISTS last_departments  TEXT DEFAULT '[]';
ALTER TABLE rag_conversation_state ADD COLUMN IF NOT EXISTS turn_count        INTEGER DEFAULT 0;
ALTER TABLE rag_conversation_state ADD COLUMN IF NOT EXISTS context_updated_at TEXT;
-- 원문 질의는 저장하지 않는다(개인정보 최소화) — 비식별 요약만.
```

## 5. 후속질의 재작성 — 규칙 우선 설계

규칙 기반(LLM 비용 0, 결정적)이 커버하는 범위를 먼저 넓힌다:

| 후속 신호 패턴 | 재작성 규칙 |
|---|---|
| "언제 병원/응급실" | `{last_symptom_name}일 때 언제 진료가 필요한가요` |
| "무슨/어느 과" | `{last_symptom_name}은 어느 과` (이미 triage 자산 재사용) |
| "약/약은/먹어도" | `{last_symptom_name} 관련 일반의약품 정보` (drug_safety 라우팅) |
| "얼마나/며칠" | `{last_symptom_name} 지속 기간` |
| "왜/원인" | `{last_symptom_name} 원인` |
| 대명사("그거/이거/그게") | last_symptom_name으로 치환 |

규칙 미스 + 모호 → LLM 1콜 폴백(시스템프롬프트: "직전 주제=X, 다음 발화를 독립 질의로 재작성"). live 환경에서만, 비용 가드.

## 6. 안전 불변식 (반드시 지킬 것)

1. **매 턴 crisis/emergency 재평가** — 이전 턴이 일반이어도 이번 턴이 응급이면 즉시 응급 분기. 문맥이 안전 분기를 *약화*시키지 않는다.
2. **재작성은 검색 질의에만** — 사용자에게 보이는 답변·면책·인용 정책은 단일 턴과 동일.
3. **이력은 비식별 요약만** — 증상키/intent/진료과. 원문 미저장. 동의 철회 시 즉시 폐기(개인화 단계의 consent 연동).
4. **재작성 추적** — rag_queries 감사에 `rewritten_from`(원 질의 해시)·`rewrite_method`(rule/llm) 기록.

## 7. 구현 순서 (Sprint 3 후반 ~ Phase 1)

1. 멀티턴 골든셋: 대화 시퀀스 20세트(증상→후속 패턴별) — 재작성 정확도 측정용
2. `conversation_context.py`: 세션 컨텍스트 로드/갱신 (rag_db 위임, SQLite/PG 양립)
3. `followup_rewriter.py`: is_followup 판정 + 규칙 재작성 (순수 함수, 테스트 가능)
4. 011 마이그레이션 + rag_routes/_rag_chat 배선 (conversation_id로 컨텍스트 주입)
5. LLM 폴백(모호 케이스) — live, 비용 가드
6. 감사 컬럼 + 골든셋 회귀 게이트

## 8. 측정 기준 (착수 게이트)

- 규칙 재작성만으로 후속질의 standalone화 정확도 ≥80%(멀티턴 골든셋)
- 안전 불변식: 멀티턴 시퀀스에서 응급/위기 재평가 100%
- 구현 전후 단일 턴 골든셋 무회귀
