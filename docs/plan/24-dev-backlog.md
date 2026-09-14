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

## 🔵 현재 — 루틴형 전환(Phase 3) · 정본 [25-routine-transition-spec](25-routine-transition-spec.md)
전략(사용자확대전략 rev6): 정보형(Q&A)은 트리거가 앱 밖 → 자연빈도 월 1회 미만. **상담에서 루틴으로** 카테고리 전환.
- ✅ **12주 프로그램 엔진**(`routine_engine.py`) — 단계 2/4/4/2, 주차×트랙 36개 기록형 행동(출처 필수), 밴드 캡(경고=0 고정), 전환 판정 70/40
- ✅ **영속·API**(`routine_repo.py`·`bff/routine_routes.py`·mig023) — 홈 1콜 `/routine/today`, 멱등 체크인(UNIQUE), 서버 KST 날짜 확정, 주간 리포트
- ✅ **프론트 4탭 재구성**(`web/js/*` 8모듈) — 오늘(행동 1개·1탭 완료)·프로그램(12주 타임라인·히트맵)·상담·내 건강. 안전규칙 8종 전량 적용
- ⏳ 남음: 12주 완주자 발생 후 **유지 모드(S12)** · 서버 푸시 발송(현재 시각 저장+인앱) · 공단 PHR 실연동(P2)
- 🟡 **루틴 팩 플랫폼화(승인 대기)** — 정본 [28-routine-pack-platform](28-routine-pack-platform.md). 커리큘럼을 코드 상수에서 팩 JSON 으로, 건강 12주는 `health_12w` 팩 1호(골든 무회귀), 골프 6개월·일본어 6개월 샘플 팩. 결정 D1~D9 승인 후 Phase 0 착수

## 🟢 P1 — 앱 완성·생산화
- ✅ **`web/` 정적 호스팅 분리** — GCS 공개버킷(`deploy-web.ps1`), 프론트 변경=Docker 빌드 0·즉시반영. BFF 는 API 전용(CORS `storage.googleapis.com`). config.js 로 BFF URL 런타임 주입(기본 빈값=same-origin 하위호환).
  - 앱: `https://storage.googleapis.com/medical-rag-web-716262961556/index.html` · 검증: cross-origin 전체 여정(인증→동의→페르소나(경고)→코칭) ACAO ALL PASS.
- **SSE 스트리밍**(타이핑 효과) · Vite 정식빌드 + openapi-typescript
- ✅ **선제 홈카드**(anticipatory_engine) + **추천질문**(suggested_questions) — `/home` 이 페르소나 밴드 신호 → 선제 'must-attend' 카드(경고→진료 referral·병원찾기) + 예상질문·태그기반 추천질문 칩. 홈 컴포넌트가 `/home` 단일 호출로 통합.
- ✅ **채팅 히스토리(영속)** — `/chat` 이 질문·답변·출처·맞춤안내를 저장(rag_db `chat_message`, conversation_id=subject_id) + `/chat/history` 복원. 홈 진입 시 이전 대화 자동 복원(인사말 대체).
- 기능 이식(남음): 푸시 리마인더

## 🟡 P2 — 개인화(실데이터)
- **PHR 공단검진 연동**(검진밴드→vital_rules) — 페르소나 데모를 실데이터로 승격
- **방향2 라이브**(밴드 라벨 LLM 주입 검증) · **국내 LLM 경로**(국외이전 제거) · personal_record 암호화 영속(mig**023+** — 017~022 점유, LAUNCH-READINESS E1 참조)
- 🟣 **[데모] 전체 PHR 원시값 LLM 주입** — `PERSONAL_RAW_TO_LLM`(기본 off) 시 밴드-온리(방향2·G6 라벨백스톱) 대신 원시 수치·PHR을 LLM 맥락에 주입(`personal_llm_context.build_raw_context`). 동의·응급·국외이전 게이트 유지. **⚠️ 합성 페르소나 데모 전용 — 실 PHR 운영 전 doc 17 재검토 필수**(원시값 노출은 방향2 컴플라 설계를 되돌림).

## 🟠 P3 — 운영·품질
- 모니터링(analytics→Metabase/Grafana) · 레이트리밋·비용/악용 제어
- KB 커버리지 확충 + ingest 수집기 배선(전개기 완성) · freshness 랭킹 · 데이터 파기 잡
- CI 배포 게이트(골든셋) · 병원 진료시간(HIRA 상세) · /healthz 404

## 🔒 후순위(지시) — 인증·세션
- PASS 실연동 · 토큰 시크릿 Secret Manager 고정 · APP_ENV=prod fail-closed (현 mock 유지)

## [신규 2026-09-10] 공용 analyzer 처방 지시 탐지 결함 (오탐보다 위험)

`ComplianceAnalyzer().analyze()` 가 아래 명백한 처방 지시에 위반을 **하나도** 내지 않는다.
RAG 는 CRITICAL 처방 위반을 하드 차단으로 처리하므로, 탐지 실패는 그대로 사용자에게 나간다.

- "메트포르민 500mg으로 올리세요."      약물명+용량+증량 지시
- "타이레놀 두 알 드세요."              제품명+개수+복용 지시
- "인슐린 용량을 2단위 늘리세요."       약물+용량단위+증량 지시
- "기존 약을 끊고 이 약으로 바꾸세요."  중단+전환 지시

정상 탐지되는 대조군: "이 약을 하루 세 번 복용하세요", "혈압약은 오늘부터 중단하세요",
"항생제를 5일간 복용하세요", "아스피린을 매일 복용하시면 됩니다".

추정 원인: 규칙이 '복용/투여' 동사에 묶여 있어 다른 지시 동사(올리세요·늘리세요·줄이세요·
드세요·바꾸세요·끊으세요)와 한국어 수량 표현(두 알, 2단위)을 놓친다.

수정 위치는 `packages/medical_shared` 의 `violation_rules.json` 이며, RAG 전용
오탐 필터(`_filter_guardrail_false_positives`)로 보상하면 안 된다(그 필터는 반대 방향).

## [신규 2026-09-14] medical-eval 온톨로지 연동 준비 (대기 — medical-eval Phase 1 이후)

참고 문서: `docs/integration/medical-eval-reference.md` (전달 사본: `medical-eval/docs/integration/rag_reference.md`, 그 저장소에는 미커밋)

medical-eval(온톨로지 기반 평가 v3) 입장에서 RAG 는 추후 연동 대상이다. 연동 시 RAG 쪽 작업:

1. CI: 온톨로지 `rule_example` 로 가드레일·오탐 필터 회귀 테스트 (금지 → 차단, 허용 → 통과)
2. STOP 메타 `ontology_version`
3. 규칙 2(d) `[일반 기준]`(모델 기억) → `render_prompt_tables` 표 주입
4. `render_raw_context` → `allowed_facts` 대체 (기능 플래그 + A/B)
5. `check_no_cross_import`: `medical_eval.ontology` 만 허용, 판정기 import 금지

연동 조사에서 드러난 RAG 결함 (연동과 무관하게 존재):

- **raw 모드에서 deny 4종(LDL·eGFR·골밀도·요단백) 미적용** — 11번 스펙 §2-B 는 개인 구간 라벨 금지인데, raw 모드는 PHR 원문을 그대로 주고 규칙 9 L1 이 구간 분류를 허용한다. 프롬프트 지시·필터 모두 없음. 선행 조치(프롬프트 지시 또는 원문 필터)로 막을지, 온톨로지 연동 때 해결할지 결정 필요.
- **`/api/service/conversations` 경로 누락** — `answer_style` 미전달, STOP 에서 `prompt_version`·`guardrail_action`·`gate_decision`·`citations` 누락(wraith 어댑터). 앱 경로에서 관찰·평가가 필요하면 어댑터 STOP 에 추가(additive).
- **`X-Personalization` 헤더 미소비** — BFF 가 보내지만 RAG 서버가 읽지 않는다. 동의 게이트는 body `personal_consent`. 계약 문서 정리 필요.
- **검진 7종 밴드(11번 스펙 §2-A) 미구현** — 온톨로지 `reference_range` 도입 시 대체 가능.
