# 23 — P0 상세 설계 (생산앱 기반: BFF + 계정 + 동의원장)

> 상태: v0.1 (2026-06-24) · 입력 = [22-production-app-plan.md](22-production-app-plan.md) 결정 5건 확정
> 확정 스택: **모바일 웹(React+PWA) · FastAPI BFF · 독립앱 · 개인화(P2 1차) · 공단검진**
> 범위: P0 = **BFF + 계정/세션 + 동의원장 MVP**(런치블로커 B 해소 토대). RAG/코칭/안전엔진은 기존 Python 자산 그대로 뒤에 둠.
> 산출 후 → 사용자 리뷰 → P0 스캐폴딩(FastAPI 서비스) 착수.

---

## 0. P0가 만드는 것 / 안 만드는 것

| 만든다 (P0) | 안 만든다 (P1+) |
|---|---|
| FastAPI BFF(Gateway): 인증·동의검증·라우팅·OpenAPI | 정식 PHR 수집(공단 OAuth 실연동 → P1) |
| 계정·세션: PASS 본인인증 → 계정 → JWT | 개인화 답변 본문(방향2) 전면화 → 동의완비 후 |
| **동의원장(consent ledger)**: append-only, 버전·철회·감사 | 게이미피케이션 실푸시(FCM/웹푸시) |
| 동의 게이트 SDK: 기존 G1~G6 를 ledger 백엔드로 승격 | 파트너 SSO·임베드 SDK(P3) |
| 최소 화면 플로우: 온보딩→동의→본인인증→홈(채팅 1개) | 적응 코칭 루프 고도화 |
| RAG `/chat` 프록시(동의 게이트 통과 시) | — |

**원칙(불변)**: 원시 측정값·진단명·원문은 결정적 로컬 엔진만, LLM/국외엔 비식별 밴드 라벨만(방향2 G1~G6). P0에서 ledger 가 그 게이트의 **진실원천**이 된다.

---

## 1. P0 아키텍처

```
[React PWA] ──HTTPS──> [FastAPI BFF] ──(내부)──> [RAG 서비스(기존 Python)]
                          │  auth·동의검증·rate                  └ generate_response
                          │  OpenAPI→TS 코드젠
                          ▼
                 [PostgreSQL: account·session·consent_*]
                          ▲
                 [PASS 본인인증(통신사) · OIDC(후순위)]
```

- BFF 와 RAG 서비스는 별 프로세스. BFF 가 동의 게이트를 **선검증**한 뒤에만 RAG 호출.
- 안전엔진(`vital_rules`·`personalization_safety`·`personal_llm_context`)은 RAG 서비스 안에 그대로. BFF 는 "이 요청에 개인화/방향2 허용되는가?"만 ledger 로 판정해 헤더로 전달.
- DB 는 기존 PG 재사용(스키마만 확장). 민감 PHR 물리분리(`personal_record_sensitive`)는 P1.

---

## 2. 동의원장 스키마 (런치블로커 B 핵심) — migration 020

> append-only 원장: **레코드를 UPDATE/DELETE 하지 않는다.** 철회 = `action='revoke'` 신규 레코드. → 전체 동의 이력·감사 추적·개인정보보호법 철회권 충족.

```sql
-- 동의 항목 정의(버전드). 약관 개정 시 version 증가, 과거 동의는 그 시점 version 에 고정.
CREATE TABLE consent_item (
  item_key      TEXT NOT NULL,        -- personal_info|sensitive_info|cross_border|location|push|phr_link
  version       INT  NOT NULL,        -- 약관/고지 버전
  title         TEXT NOT NULL,
  body_url      TEXT,                 -- 동의서 본문(고지) 링크
  required      BOOLEAN NOT NULL,     -- 필수(거부 시 가입 불가) 여부
  effective_at  TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (item_key, version)
);

-- 동의 원장(append-only). 한 주체×항목에 대해 grant/revoke 레코드가 시간순 누적.
CREATE TABLE consent_record (
  id            UUID PRIMARY KEY,
  subject_id    UUID NOT NULL,        -- account.id
  item_key      TEXT NOT NULL,
  item_version  INT  NOT NULL,
  action        TEXT NOT NULL,        -- 'grant' | 'revoke'
  source        TEXT NOT NULL,        -- 'onboarding'|'settings'|'reconsent'
  created_at    TIMESTAMPTZ NOT NULL,
  evidence_hash TEXT,                 -- 고지문구+버전 해시(무엇에 동의했는지 고정)
  FOREIGN KEY (item_key, item_version) REFERENCES consent_item(item_key, version)
);
CREATE INDEX ix_consent_record_subject ON consent_record(subject_id, item_key, created_at DESC);
```

**현재 유효 상태** = 주체×항목별 최신 `created_at` 레코드의 action 이 `grant` 인지(쿼리 또는 `consent_current` materialized view). 게이트는 이걸 본다.

동의 항목(P0 6종):
| item_key | 필수 | 게이트하는 것 |
|---|---|---|
| personal_info | ✅ | 서비스 이용 전반 |
| sensitive_info | — | 개인화(건강 라벨)·방향2 본문 |
| cross_border | — | 국외 LLM 이전(G4); 국내 LLM 이면 불필요 |
| location | — | 시설 finder geolocation |
| push | — | 코칭 리마인더(정보통신망법) |
| phr_link | — | 공단검진 연동(P1 실연동) |

---

## 3. 계정·세션 — migration 021

```sql
CREATE TABLE account (
  id            UUID PRIMARY KEY,
  ci            TEXT UNIQUE,          -- 본인인증 연계정보(CI) 해시 — 중복가입 식별
  di_hash       TEXT,                 -- DI(서비스별) 해시
  status        TEXT NOT NULL,        -- active|dormant|withdrawn
  created_at    TIMESTAMPTZ NOT NULL,
  withdrawn_at  TIMESTAMPTZ
);
CREATE TABLE auth_session (
  id            UUID PRIMARY KEY,
  subject_id    UUID NOT NULL REFERENCES account(id),
  refresh_hash  TEXT NOT NULL,        -- refresh 토큰 해시
  device        TEXT,
  issued_at     TIMESTAMPTZ NOT NULL,
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ
);
```

- **본인인증**: PASS(통신사) 표준창 → CI/DI 수신 → account upsert(CI 기준 중복 식별). P0는 PASS 1종, OIDc/소셜은 후순위.
- **세션**: access(JWT, 단명 15m) + refresh(회전, DB 해시 저장). 로그아웃·철회 시 `auth_session.revoked_at`.
- CI 는 **해시 저장**(원본 비보관), 민감 식별자 암호화 컬럼.

---

## 4. BFF API 계약 (P0 엔드포인트)

> 전부 FastAPI + Pydantic 모델. OpenAPI 자동생성 → 프론트 `openapi-typescript` 로 타입드 클라이언트.

| 메서드 | 경로 | 설명 | 동의 게이트 |
|---|---|---|---|
| POST | `/auth/pass/start` | PASS 인증창 트랜잭션 시작 | — |
| POST | `/auth/pass/callback` | CI/DI 수신→계정·세션 발급 | — |
| POST | `/auth/refresh` | 토큰 회전 | 세션 |
| POST | `/auth/logout` | 세션 폐기 | 세션 |
| GET | `/me` | 계정·동의 현황 요약 | 세션 |
| GET | `/consent/items` | 현행 항목·버전·고지 | — |
| POST | `/consent` | grant/revoke (append) | 세션 |
| GET | `/consent/history` | 동의 이력(감사) | 세션 |
| POST | `/chat` | RAG 프록시(SSE) | personal_info; 개인화는 sensitive_info+(국외 시 cross_border) |
| GET | `/home` | 선제 카드(Anticipatory) | personal_info |
| DELETE | `/me` | 회원 탈퇴(원장 보존·계정 withdrawn) | 세션 |

**`/chat` 게이트 로직(BFF)**: `consent_current(subject, 'personal_info')` 없으면 401 동의요구. 개인화 신호 주입은 `sensitive_info` grant 시에만, 국외 LLM 경로면 `cross_border` 까지 확인 → RAG 에 `X-Personalization: on|off` + `X-Cross-Border-Ack: 0|1` 헤더로 전달(기존 G2/G4 를 ledger 로 승격).

---

## 5. 기존 자산 → P0 매핑

| 기존(프로토타입) | P0 위치 | 변경 |
|---|---|---|
| `personal_consent`/`coaching_consent` 게이트 인자 | BFF 가 ledger 조회 후 헤더 주입 | 게이트 **판정원**이 localStorage→ledger |
| `personal_llm_context` G1~G6 | RAG 서비스 유지, 입력은 BFF 헤더 | G2(동의)·G4(국외) 소스만 교체 |
| `rag_engine.generate_response` | RAG 서비스 그대로 | BFF 가 프록시 |
| `/app` Warm Light SPA | React PWA 출발점 | 컴포넌트화·세션 연동 |
| `analytics_events` | 그대로(비식별) | consent_* 이벤트 추가 |

---

## 6. 화면 플로우 (P0 최소)

```
스플래시 → (미온보딩) 온보딩 3p → 동의(필수+선택 토글, 고지링크)
        → PASS 본인인증 → 홈
홈: [선제 카드 1] [의료 채팅 입력] [내 정보/동의관리]
설정 → 동의관리(현행 grant/revoke + 이력) · 탈퇴
```

- 동의 화면: 필수(personal_info) 미동의 시 진행 불가. 선택은 토글. 각 항목 고지문 링크 + evidence_hash 기록.
- 철회: 설정에서 즉시 revoke → 다음 요청부터 게이트 OFF(개인화 중단). UI 에 "철회 시 개인화 중단" 고지.

---

## 7. 마이그레이션·테스트·빌드 순서

- **migrations**: 020 consent_item+consent_record / 021 account+auth_session (PG+`_sqlite` 듀얼, 기존 러너 규칙; 주석에 세미콜론 금지).
- **테스트**: ① consent ledger 순수 로직(grant→revoke→current 판정, 버전 고정) ② BFF 게이트(개인화 허용/차단 매트릭스) ③ auth 콜백(중복 CI=동일계정) ④ `/chat` 프록시 게이트. 모두 DB=SQLite.
- **빌드 순서(P0 DAG)**:
  1. migration 020/021 + `consent_db.py`(순수 판정 + DB) + 테스트
  2. FastAPI 앱 골격 + `/consent/*` + `/me` + 테스트
  3. PASS 어댑터(목 → 실연동) + `/auth/*`
  4. `/chat` 프록시 + 게이트 헤더 + RAG 연동
  5. React PWA: 온보딩·동의·세션·채팅 1화면 + openapi-typescript
  6. 관측: consent_grant/revoke analytics 이벤트

---

## 8. 컴플라이언스 체크(P0 종료 게이트)

- [ ] 필수 동의 미취득 시 개인화·민감처리 **구조적 차단**(테스트로 고정)
- [ ] 철회 즉시 반영(다음 요청 게이트 OFF) + 이력 보존
- [ ] CI/민감식별자 암호화·해시, 원문 비보관
- [ ] 국외이전 동의 없으면 국외 LLM 경로 차단(국내 LLM 기본)
- [ ] 동의서 버전·evidence_hash 로 "무엇에 동의했는지" 재현 가능
- ⚠ 런치블로커 **A(의료법 변호사검토)** 는 P0 산출물 아님 — 개인화 ON 출시 전 별도. P0는 비개인화로도 기동 가능하게(personal_info 만으로 RAG 정보제공).

> 다음: 사용자 리뷰 → 빌드 순서 1번(migration 020/021 + consent_db.py)부터 P0 스캐폴딩 착수.
