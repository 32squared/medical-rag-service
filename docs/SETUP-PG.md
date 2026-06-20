# 로컬 PostgreSQL(pgvector) 셋업 — RAG end-to-end

라이브 검색(`hybrid_search`)은 **pgvector + tsvector**라 PostgreSQL이 필요하다.
PG를 확보(아래 A/B/C 중 택1)한 뒤 **`.env`에 `DATABASE_URL`을 넣고** 한 줄로 끝낸다:

```bash
python setup_local_pg.py      # 마이그레이션 + 시드 + 스모크(실검색)
python rag_server.py          # API 서버 기동
```

---

## PG 확보 경로 (택1)

### A. 클라우드 무료 PG — 설치 불필요(가장 쉬움)
[Neon](https://neon.tech) 또는 [Supabase](https://supabase.com) 무료 플랜. 둘 다 pgvector 지원.
1. 가입 → 프로젝트 생성 → **Connection string** 복사
2. `.env`에 추가:
   ```
   DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
   ```
3. `python setup_local_pg.py`
> Neon은 `CREATE EXTENSION vector`가 기본 허용. Supabase는 대시보드 Database→Extensions에서 `vector` 활성화.

### B. Docker (로컬, 재현성 좋음) — Docker Desktop 필요
```bash
docker run -d --name medrag-pg -e POSTGRES_PASSWORD=dev -p 5432:5432 pgvector/pgvector:pg16
```
`.env`: `DATABASE_URL=postgresql://postgres:dev@localhost:5432/postgres`
→ `python setup_local_pg.py`

### C. 네이티브 설치 — Windows
1. PostgreSQL 16 설치([EDB 인스톨러](https://www.postgresql.org/download/windows/))
2. pgvector 설치(미리빌드 DLL 또는 `make`) → `CREATE EXTENSION vector;`
3. `.env`에 `DATABASE_URL` 설정 → `python setup_local_pg.py`
> 네이티브 pgvector는 손이 많이 간다. 빠른 시험은 A(클라우드) 권장.

---

## 셋업 후 확인
- `setup_local_pg.py`의 4단계 스모크가 `'두통' → N건`을 출력하면 검색 동작.
- 라이브 답변 생성에는 `OPENAI_API_KEY`(이미 .env에 적용됨) + **계정에 존재하는 모델**이 필요:
  ```
  RAG_LLM_MODEL=gpt-4o-mini      # 계정 모델 목록에 맞춰 조정
  ```
- 서버: `python rag_server.py` → `POST /api/rag/chat`(SSE), `/api/service/conversations/{graph_type}`,
  `/api/data_management/conversations|projects` (wraith 호환).

## 트러블슈팅
- `NotImplementedError ... PostgreSQL`: DATABASE_URL 미설정 → SQLite 모드. `.env` 확인.
- `extension "vector" is not available`: 관리형 PG에서 pgvector 비활성 → 대시보드에서 활성화.
- 시드 0건/검색 0건: `python collect_public_kb.py --source all`(공공 KB, 키 필요) 또는 `seed_kb_expansion.py` 재실행.
