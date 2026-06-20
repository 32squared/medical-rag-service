# RAG 테스트 가이드

이 RAG는 **두 가지 방식**으로 시험할 수 있다. 외부 의존이 없는 ①번이 즉시 실행 가능하다.

## ① 오프라인 (지금 바로 — PG·OpenAI 불필요)

규칙기반 분류·안전분기·진료과 트리아지·거절→길안내·인용검증·멀티턴 후속질의
재작성을 mock LLM으로 즉시 시험한다. 실검색(임베딩)·실LLM 생성은 제외.

```bash
python rag_try.py "배가 아파요"            # 단발 질의
python rag_try.py                          # 대화형 REPL (멀티턴: 이어지는 질문에 직전 주제 적용)
python rag_try.py --examples               # 대표 5개 질의 일괄(멀티턴 carry 포함)
python rag_try.py --json "두통"            # 결과 전체 JSON
```

확인 포인트:
- "숨을 못 쉬겠어요"/"가슴이 너무 조여요" → `emergency` + 119 안내 (구어체·부사삽입 도달)
- "죽고 싶어요" → `mental_health_crisis` + 109 안내
- "배가 아파요" → 근거부족이어도 진료과 길안내(거절 최소화)
- REPL에서 "머리가 아파요" 후 "약은 먹어도 되나요?" → 직전 주제(두통)로 재작성

## ①-b 로컬 웹 UI로 클라우드 RAG 눌러보기 (브라우저)

배포된 dev 서비스를 브라우저 채팅 화면에서 시험한다. 로컬 프록시가 gcloud
IAM 토큰을 자동 부착해 Cloud Run으로 중계(SSE 스트리밍)한다.

```bash
python local_test_ui.py          # → http://localhost:8765 접속
```
- 전제: `gcloud` 로그인(현재 계정). 토큰 자동 발급·캐시.
- 대상 변경: `python local_test_ui.py --rag-url https://...run.app`
- 질문 입력 → 실시간 생성 답변 + 근거/인용 표시. 대화는 멀티턴 유지.

## ② 전체 자동화 테스트 (CI)

```bash
python -m pytest -q          # 447 pass, 12 skipped (skip = PG 필요한 integration)
```

골든셋 회귀 게이트: `tests/golden/golden_set.json`(증상·안전 도달),
`tests/golden/multiturn_golden.json`(후속질의 재작성 ≥80%).

## ③ 라이브 (실검색 + 실LLM — PostgreSQL + OpenAI 필요)

`hybrid_search`는 PostgreSQL 전용(SQLite는 NotImplementedError)이므로 라이브
end-to-end는 아래가 필요하다.

1. **PostgreSQL** + `DATABASE_URL` 설정 (pgvector 확장).
2. **스키마/시드**:
   ```bash
   python migrations/migrate_runner.py --sync       # 전체 마이그레이션
   python seed_kb_expansion.py                       # KB 시드 적재
   ```
3. **LLM 키**: `OPENAI_API_KEY` (분류·생성). 미설정 시 규칙기반 분류 + 빈 생성.
4. **서버 실행**: `python rag_server.py` → `POST /api/rag/chat` (SSE).
   - 인터페이스: [docs/api/INTERFACE.md](api/INTERFACE.md)
5. **공공 KB 수집**(선택): `python collect_public_kb.py --source all`
   (KDCA/MFDS 등은 `KDCA_API_KEY`/`DATA_GO_KR_KEY` 필요. 0건/급감은 수집 건전성 경고로 표면화).

> 라이브 경로의 실제 답변 생성은 `rag_engine.generate_response`(SSE)이며,
> 오프라인 하니스(`rag_try.py`)는 `medical_rag_pipeline.process_medical_query`를 쓴다.
> 둘 다 같은 규칙 모듈(분류·매칭·안전·인용·멀티턴)을 공유한다.
