# 24 — 개발 백로그·순서 (살아있는 문서)

> P0 BFF/web 배포 이후 **엔지니어링 작업**의 우선순위·순서. 법률(A)·의료검수(D)는 [LAUNCH-READINESS](../LAUNCH-READINESS.md).
> 운영방식: `/loop 20m` 자율 개발 — 증분 자동커밋, 테스트보다 **개발 중심**. 인증/세션은 mock 유지(후순위).

## ✅ 완료(라이브 검증) — 페르소나 기반 개인화 데모 (loop 4fb3012a)

회원가입 → **페르소나 1개 선택**(24종, 합성 vitals/PHR) → 그 신호로 **개인화 질의응답 + 개인화 게이미피케이션** 체험. (실 PHR 대체 = 데모로 개인화를 켤 수 있음)
> 검증: 리비전 `medical-rag-bff-00003-stj`(06-25 04:03 KST) — `/personas`(24종)·`/persona/select`(밴드 경고)·코칭 배너+캡·done_today/streak·병원약국 real=True 8곳 all PASS.

1. ✅ 인용 링크·문진·코칭(영속)·병원약국 실검색 *(직전)*
2. ✅ **페르소나 선택·영속** — BFF `/personas`·`/persona/select`·`/persona` + `subject_profile`(account_db) 영속
3. ✅ **페르소나 → 개인화 채팅** — 선택 시 `build_agent_input(persona)`를 RAG 에 전달(agent_input_field_to_value) + 밴드 계산 → personalization on
4. ✅ **페르소나 → 개인화 코칭** — 페르소나 worst_band → `generate_plan(track,intake,band)`(밴드 배너·캡) + 게이미피케이션(streak)
5. ✅ **web 페르소나 화면** — 온보딩 후 선택 카드(이름·이모지·프로필·예시질문) + 홈 '현재 페르소나' 표시 + 페르소나 추천 질문 칩

## 🟢 P1 — 앱 완성·생산화
- ✅ **`web/` 정적 호스팅 분리** — GCS 공개버킷(`deploy-web.ps1`), 프론트 변경=Docker 빌드 0·즉시반영. BFF 는 API 전용(CORS `storage.googleapis.com`). config.js 로 BFF URL 런타임 주입(기본 빈값=same-origin 하위호환).
  - 앱: `https://storage.googleapis.com/medical-rag-web-716262961556/index.html` · 검증: cross-origin 전체 여정(인증→동의→페르소나(경고)→코칭) ACAO ALL PASS.
- **SSE 스트리밍**(타이핑 효과) · Vite 정식빌드 + openapi-typescript
- ✅ **선제 홈카드**(anticipatory_engine) + **추천질문**(suggested_questions) — `/home` 이 페르소나 밴드 신호 → 선제 'must-attend' 카드(경고→진료 referral·병원찾기) + 예상질문·태그기반 추천질문 칩. 홈 컴포넌트가 `/home` 단일 호출로 통합.
- 기능 이식(남음): 채팅 히스토리(영속) · 푸시 리마인더

## 🟡 P2 — 개인화(실데이터)
- **PHR 공단검진 연동**(검진밴드→vital_rules) — 페르소나 데모를 실데이터로 승격
- **방향2 라이브**(밴드 라벨 LLM 주입 검증) · **국내 LLM 경로**(국외이전 제거) · personal_record 암호화 영속(mig017+)

## 🟠 P3 — 운영·품질
- 모니터링(analytics→Metabase/Grafana) · 레이트리밋·비용/악용 제어
- KB 커버리지 확충 + ingest 수집기 배선(전개기 완성) · freshness 랭킹 · 데이터 파기 잡
- CI 배포 게이트(골든셋) · 병원 진료시간(HIRA 상세) · /healthz 404

## 🔒 후순위(지시) — 인증·세션
- PASS 실연동 · 토큰 시크릿 Secret Manager 고정 · APP_ENV=prod fail-closed (현 mock 유지)
