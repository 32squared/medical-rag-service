# 마이헬스케어 P0 BFF (FastAPI)

정본: [docs/plan/23-p0-detailed-design.md](../docs/plan/23-p0-detailed-design.md).
엣지 게이트웨이 — 본인인증·동의검증·RAG 프록시. 기존 Python 자산(안전엔진·RAG·
`consent_db`·`account_db`)을 그대로 뒤에 둔다. **경계 불변**: 원시 측정값·진단명·원문은
RAG 서비스 내부 결정엔진만 보고, BFF 는 동의 판정 결과를 **헤더로만** 전달한다.

## 실행

```bash
uvicorn bff.app:app --host 0.0.0.0 --port 8080
# 개발: uvicorn bff.app:app --reload
```

## 환경변수

| 변수 | 용도 | 기본/주의 |
|---|---|---|
| `APP_ENV` | 환경(`prod`/`dev`) | `prod` 이면 아래 보안설정 **fail-closed**(누락/기본값이면 부팅·서명·해시 거부) |
| `BFF_TOKEN_SECRET` | access 토큰 HMAC 서명키 | prod 필수(미설정/dev기본키 → prod에서 RuntimeError) |
| `ACCOUNT_CI_HMAC_KEY` | CI/DI 해시 HMAC 키 | prod 필수(미설정 → prod에서 RuntimeError, dev는 SHA256 폴백+경고) |
| `PASS_PROVIDER` | 본인인증 provider | `mock`(P0). prod에서 mock 은 `ALLOW_MOCK_AUTH=1` 없으면 차단 |
| `ALLOW_MOCK_AUTH` | prod mock 허용 플래그 | 설정 시에만 prod mock 인증 허용(스테이징용) |
| `RAG_URL` | RAG 서비스 베이스 URL | `.run.app` 이면 SA 메타데이터 토큰 자동첨부 |
| `RAG_GRAPH` | RAG 대화 그래프명 | `medical_rag` |
| `DB_PATH` / `DATABASE_URL` | SQLite / PostgreSQL | dbcommon 공용 |

**보안(감사 반영)**: prod fail-closed 설정검증(부팅 시) · access 토큰은 live 세션+active 계정 필수(탈퇴/로그아웃 즉시 무효) · refresh **1회용 회전**(재사용 차단) · 탈퇴 재로그인=재동의 강제 · 국외이전 ack 는 **동의원장 기준**(클라 flag 단독 불가) · 빈 CI 거부.

## 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/healthz` | — | 헬스체크 |
| POST | `/auth/pass/start` | — | 본인인증창 트랜잭션 시작 |
| POST | `/auth/pass/callback` | — | CI/DI→계정·세션→토큰 발급 |
| POST | `/auth/refresh` | refresh | access 재발급(session_id+refresh) |
| POST | `/auth/logout` | 세션 | 세션 철회(access 즉시 무효) |
| GET | `/consent/items` | — | 현행 동의 항목·필수여부 |
| POST | `/consent` | 세션 | grant/revoke(append-only 원장) |
| GET | `/consent/history` | 세션 | 동의 이력(감사) |
| GET | `/me` | 세션 | 계정·동의현황·미취득 필수 |
| DELETE | `/me` | 세션 | 탈퇴(status=withdrawn, 세션철회, 이력보존) |
| POST | `/chat` | 세션 | RAG 프록시(동의게이트) |
| GET | `/home` | 세션 | 선제 카드(personal_info 필요) |

### 동의 게이트(핵심)
- `/chat`·`/home` 은 **personal_info** 동의 필수(없으면 403).
- 개인화(방향2 본문 맞춤)는 **personal_info AND sensitive_info**, 국외 LLM 경로(`cross_border:true`)면 **cross_border** 동의까지. 판정원=`consent_db` 동의원장 실시간 조회.
- 로그아웃·탈퇴=세션 철회 → 미만료 access 토큰도 즉시 무효(세션 활성 검사).

## 프론트엔드 타입(openapi-typescript)

FastAPI 가 OpenAPI 를 자동 노출(`/openapi.json`). 프론트(React+PWA)는 코드젠으로 타입드 클라이언트 확보:

```bash
# BFF 기동 후
npx openapi-typescript http://localhost:8080/openapi.json -o web/src/api/schema.ts
```

(결정 §22-9.1: 단일언어 컴플라이언스 감사성 + 이 코드젠으로 Node 없이 FE↔BE 타입 안전.)

## 상태
P0 빌드순서(doc23 §7) 2·3·4·6 구현. 미구현: PASS 실연동(현 mock), React PWA 프론트(빌드순서 5), 레이트리밋·CORS 정책(운영 강화).
