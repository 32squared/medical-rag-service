# 오늘의 나 — 기존 앱 통합 계획 (현황 점검 + 단계별 계획)

작성 2026-09-03. 브랜치 `feat/medical-reach-and-kb-expansion` 기준. 전체 테스트 893 통과 · 12 skip.

## 1. 현재 개발 상황 점검

### 1-1. 무엇이 있나

| 영역 | 현재 상태 | 근거 |
|---|---|---|
| 프론트 | Preact 10 + htm, 빌드 없음(importmap CDN). 4탭 셸(오늘·프로그램·상담·내 건강) + 온보딩(환영→동의→PASS 목→페르소나→루틴 시작). 라우터 없음, `useState` 단계 머신 | `web/js/app.js:16-35` |
| 스타일 | `web/index.html` 한 파일에 CSS 전부. 토큰: `--bg #F6F4EF`, `--teal #0E8A6B`, `--radius 16px`. 서체 Pretendard | `web/index.html:15-304` |
| 홈 데이터 | `GET /routine/today` 1콜로 프로그램·오늘 행동·주간·히트맵·코치·배너·안전 | `bff/routine_routes.py:175-249` |
| 체크인 | `POST /routine/checkin` done/skip/na/undone, 멱등키, E01 자정 유예, 되돌리기 | `bff/routine_routes.py:299` |
| 밴드 | `vital_rules` → `worst_band()`. 응급 시 `_emergency()` 차단 | `bff/app.py:106-118` |
| 동의 게이트 | `_require_personal()` 403 `personal_info_consent_required` | `bff/routine_routes.py:95` |
| 저장소 | `routine_program / routine_checkin / routine_report / routine_notify_pref`, 마이그레이션 023(sqlite·PG 각각) | `routine_repo.py:54-82` |
| 게임 요소 | 홈 헤더 🔥 연속 칩, 프로그램 탭 🏅 배지 행, 포인트·레벨은 페이로드에만 있고 미렌더 | `today.js:166`, `program.js:78-80` |
| 분석 | `EVENT_NAMES` allowlist. 미등록 이벤트는 `emit()`이 버림 | `analytics_events.py:47-64` |
| 테스트 | 88파일. `test_routine.py` 22건 통과. **CI는 21개 파일만 골라 돌리며 routine·bff 테스트가 빠져 있음** | `.github/workflows/ci.yml` |
| 배포 | Cloud Run(BFF·RAG) + GCS 정적(web). `deploy-web.ps1`이 `config.js`에 BFF URL 주입. SW 캐시 `mhc-shell-v3` | `deploy-*.ps1`, `web/sw.js` |
| 백로그 잔여 | 유지 모드 S12, 서버 푸시, 공단 PHR 실연동, SSE, Vite 전환, 모니터링, 실 PASS 인증 | `docs/plan/24-dev-backlog.md:19-43` |

### 1-2. 통합에 걸리는 간극 (반드시 결정·해결)

| # | 간극 | 영향 | 처리 |
|---|---|---|---|
| G1 | **비주얼 세계가 둘**: 기존은 크림·틸·Pretendard의 차분한 의료 톤, 재미 레이어는 캔디 파스텔·Lexend/Jua | 같은 앱에 두 톤이 섞이면 조잡해짐 | §2 D1 결정 필요. 추천: 하이브리드 |
| G2 | **걸음 자동 연동 불가**: PWA는 HealthKit·Health Connect 접근 불가. 걸음 수집 코드 0건 | FR-T1-03·FR-C07 그대로는 구현 불가 | v1 걸음 **수동 입력**(또는 활동 분). 자동 연동은 네이티브 래퍼(Capacitor) 단계로 이관 |
| G3 | **이미지 렌더 없음**: Pillow·playwright 없음, 서버 PNG 경로 없음 | 공유 카드 FR-T4-08 | v1 **클라이언트 canvas 렌더** + Web Share API(파일) → 실패 시 다운로드. 서버 렌더는 P2 |
| G4 | 기존 🔥·🏅 이모지와 배지 행 | design.md "이모지 금지", 정본 안티골(배지·레벨) | 🔥 칩은 SVG 아이콘으로 교체, 🏅 배지 행은 재미 레이어 도입 시 제거(경고 밴드 규칙과도 충돌) |
| G5 | 토큰 충돌: `--radius 16px` vs 새 24/28/32, `--tabh 62` vs nav 64 | 카드 모양이 화면마다 다름 | 토큰 이름을 분리(`--r-*`)해 공존, 기존 화면은 단계적 이관 |
| G6 | 서체 로드: Pretendard만 있음 | Lexend·Jua·Gowun Dodum 미로드 시 Malgun 폴백 | `index.html`에 Google Fonts 링크 추가, `deploy-web.ps1` CORS 무관(폰트는 googleapis) |
| G7 | CI가 routine·bff 테스트를 안 돌림 | 새 기능 회귀 감지 불가 | CI 목록에 `test_routine.py`, `test_bff_*.py`, 신규 테스트 추가 |
| G8 | 온보딩 순서에 문진 자리 없음 | 웰니스 타입 배정 | `StartRoutine` 직후, 건너뛰기 가능한 1단계로 삽입 |
| G9 | 개인정보 동의 범위 | 물·걸음·마음챙김도 건강 관련 기록 | 루틴과 동일하게 `_require_personal()` 적용 |
| G10 | `docs/design/` 26파일이 미커밋 | 팀 공유 불가 | Phase 0에서 커밋 |

## 2. 결정 사항 (착수 전)

| # | 결정 | 추천안 | 대안 |
|---|---|---|---|
| D1 | 비주얼 통합 범위 | **하이브리드**: 오늘 탭 상단(행동 카드·트랙 타일)과 재미 레이어 화면(기록·리빌·카드·타입)은 캔디 시스템, 상담·내 건강·설정은 기존 크림·틸 유지. 공통 토큰(버튼 알약, 라운드 ≥24, 탭바)만 먼저 통일 | A. 전체 재스타일(2주 추가) / B. 재미 레이어만 다른 톤(일관성 포기) |
| D2 | 걸음 v1 | **수동 입력**(타일 탭 → 숫자 입력 시트, 1,000 단위 스텝퍼). 캡션 "연동은 곧 지원" 금지, 그냥 입력 UI만 | 활동 분(10분 단위)으로 대체 |
| D3 | 카드 렌더 | **클라이언트 canvas**(1080×1920 / 1080×1080 오프스크린 캔버스, 폰트 `document.fonts.load` 후 그리기) + `navigator.share({files})` → 미지원 시 `<a download>` | 서버 렌더(P2, 헤드리스 필요) |
| D4 | 문진 위치 | `StartRoutine` 완료 → 문진 4문항 → 결과 → 홈. 건너뛰면 `type_id=null`, 설정에서 나중에 | 온보딩 맨 앞 |
| D5 | 브랜치 | 새 브랜치 `feat/todays-me-fun-layer`를 현재 브랜치에서 분기. Phase마다 PR | 현재 브랜치에 계속 |
| D6 | 배지 행 | 제거 | 경고 밴드에서만 숨김 |

## 3. 단계별 통합 계획

각 Phase는 독립 배포 가능하도록 끊었다. 괄호는 1인 기준 공수.

### Phase 0 — 준비 (1~2일)

| 작업 | 파일 | 완료 기준 |
|---|---|---|
| 설계 문서 커밋, 브랜치 분기 | `docs/design/todays-me-mockups/*` | PR #0 |
| 마이그레이션 024 (5테이블, sqlite·PG) | `migrations/024_fun_layer.sql`, `024_fun_layer_sqlite.sql` | `migrate_runner --status` 통과 |
| 이벤트 등록 | `analytics_events.py` `EVENT_NAMES`, prop allowlist에 `archetype_id, type_id, channel, format, metric, cta_variant` 등 | `test_analytics_events.py` 확장 |
| CI 목록 보강 | `.github/workflows/ci.yml` | routine·bff 테스트 CI에서 실행 |
| 서체·토큰 추가 | `web/index.html`: Google Fonts 링크, `design.md §5` 토큰 블록을 `:root`에 병합(기존 토큰 유지) | 기존 화면 픽셀 변화 0 |

### Phase 1 — 백엔드 지표·아키타입 (5~6일)

| 작업 | 파일 | 완료 기준 |
|---|---|---|
| `archetype_engine.py`: `GOALS`, 완료 판정, 7조합, 환산 사전, 하이라이트, 취침 귀속 | 신규 | 단위 테스트 30+ (`tests/test_archetype_engine.py`) |
| `metrics_repo.py`: `daily_metrics`·`archetype_result` CRUD, 7일 조회 | 신규 | sqlite·PG 양쪽 테스트 |
| `bff/metrics_routes.py`: `PUT /metrics/today`, `GET /metrics/day`, `GET /archetype/day`, `POST /archetype/seen`, 밴드 게이트 403 | 신규, `bff/app.py:531` 옆에 register | `tests/test_metrics_routes.py` |
| `GET /routine/today` 확장: `tracks / archetype / safety.fun_layer` | `bff/routine_routes.py:175-247` 빌더 끝에 블록 추가 | 기존 키 불변 스냅샷 테스트 |
| E01 유예 재사용 | `routine_routes.py` 기존 `applied_date` 로직을 `metrics_routes`에서 import | 23:55→전날 테스트 |

### Phase 2 — 프론트 화면 1·2 (5~6일)

| 작업 | 파일 | 완료 기준 |
|---|---|---|
| `normToday()`에 `tracks/archetype/safety` 정규화 | `web/js/ui.js:114-171` | 필드 누락 시 기본값 |
| 오늘 탭: 행동 카드 캔디 재스타일, 트랙 타일 3개, 컵 그리드·걸음 입력·1분 타이머 시트, 티저, "오늘의 기록 보기" CTA | `web/js/today.js` (+ 신규 `tracks.js`) | Main.dc.html과 픽셀 대조 |
| 🔥 칩 → SVG, 🏅 배지 행 제거 | `today.js:166`, `program.js:78-80` | 이모지 0 |
| 오늘의 기록 화면 | 신규 `web/js/stats.js`, `app.js` 오버레이 `stats` 추가 | Stats.dc.html 대조, CTA 4변형 |
| 오프라인 큐: 지표 입력 `idempotency_key` 재전송 | `api.js` | 오프라인 → 온라인 복귀 시 1회 전송 |
| SW 캐시 버전 | `web/sw.js` `mhc-shell-v4` | 구버전 사용자 갱신 |

### Phase 3 — 리빌·공유 카드 (6~8일)

| 작업 | 파일 | 완료 기준 |
|---|---|---|
| 리빌 화면: 3단계 연출, 건너뛰기, 태그, 희귀도, 7일 컬렉션 | 신규 `web/js/reveal.js` | ≤2.5s, reduced-motion |
| 아키타입 7종 SVG 사전 + 슬롯 글리프 | 신규 `web/js/archetypes.js` | 7키 일치 |
| `share_card` 테이블·API (`POST/PATCH /card`, 잠금 00:10) | `metrics_repo.py`, `bff/metrics_routes.py` | 00:11 PATCH 409 |
| 카드 화면 + canvas 렌더러(화이트리스트 클라 복제) + 공유(Web Share/다운로드) | 신규 `web/js/card.js`, `cardRender.js` | 골든 이미지 비교(수동), 금지 키 테스트 |
| 희귀도 배치 | `scripts/archetype_stats.py` + Cloud Run job | 월 1일 재계산 |

### Phase 4 — 웰니스 타입 (3~4일)

| 작업 | 파일 | 완료 기준 |
|---|---|---|
| `wellness_type` 테이블·API·문진 상수 | `metrics_repo.py`, `bff/metrics_routes.py` | 동점 규칙 테스트 |
| 온보딩 문진 4문항 + 결과 화면 + 타입 카드 | `web/js/onboard.js` 단계 추가, 신규 `typecard.js` | TypeResult/TypeCard 목업 대조 |
| 설정 "내 웰니스 타입" 변경 | `web/js/health.js` SettingsView | 변경 즉시 카드 라벨 반영 |
| 5종 일러스트 번들 | `web/img/type-*.jpg` (600px) | GCS 배포 포함 |

### Phase 5 — 하드닝·배포 (3일)

| 작업 | 완료 기준 |
|---|---|
| 밴드 게이트 E2E(경고 페르소나로 4화면 진입점 미노출·API 403) | 테스트 통과 |
| 카피 lint: 정본 금칙 6종·글자수 예산 CI 검사(`compliance_check` 확장) | 신규 카피 전부 통과 |
| 접근성: 200% 폰트, aria-live, 탭 44px | 수동 체크리스트 |
| `deploy-web.ps1`·`deploy-bff.ps1`로 스테이징 배포, CORS 확인 | 스테이징 URL에서 4화면 흐름 완주 |

총 공수 약 **4~5주**(1인). 백엔드(Phase 1)와 프론트 토큰·타일(Phase 2)은 목 응답으로 병렬 가능해 2인이면 3주.

## 4. 파일 변경 지도

| 구분 | 파일 | 변경 |
|---|---|---|
| 수정 | `bff/routine_routes.py` | 빌더에 3블록 추가(:175-247), E01 헬퍼 export |
| 수정 | `bff/app.py` | `metrics_routes.register` 추가(:531 인접) |
| 수정 | `analytics_events.py` | 이벤트·속성 allowlist |
| 수정 | `web/index.html` | 폰트 링크, 토큰 병합, 새 컴포넌트 CSS |
| 수정 | `web/js/ui.js`, `today.js`, `program.js`, `onboard.js`, `health.js`, `app.js`, `api.js`, `sw.js` | 위 Phase별 |
| 신규 | `archetype_engine.py`, `metrics_repo.py`, `bff/metrics_routes.py`, `migrations/024_*`, `scripts/archetype_stats.py` | 백엔드 |
| 신규 | `web/js/tracks.js`, `stats.js`, `reveal.js`, `archetypes.js`, `card.js`, `cardRender.js`, `typecard.js`, `web/img/type-*.jpg` | 프론트 |
| 신규 | `tests/test_archetype_engine.py`, `test_metrics_routes.py`, `test_card_whitelist.md`… | 테스트 |
| 불변 | `routine_repo.py` 테이블, `routine_checkin` 로직, `coaching_gamification.py`(미사용) | — |

## 5. 리스크와 완화

| 리스크 | 완화 |
|---|---|
| 두 톤 혼재로 앱이 조잡해짐 | D1 하이브리드 + 공통 토큰 우선 통일. Phase 2 끝에 4탭 스크린샷 리뷰 |
| 클라이언트 canvas의 폰트 미로드로 카드 글꼴 깨짐 | `document.fonts.load()` 완료 후 렌더, 실패 시 Malgun 폴백 + 숫자 축소 −15% |
| 수동 걸음 입력의 낮은 사용률 | 걸음 미입력도 아키타입 계산에 불이익 없음(완료 조합만). 활동 분 대체 입력 허용 |
| 정본 금칙 위반 카피 유입 | Phase 5 카피 lint를 PR 게이트로 |
| SW 캐시로 구버전 JS 잔존 | 캐시 키 버전 업 + `config.js` 제외 유지 |
| 경고 밴드 사용자에게 재미 요소 노출 | 서버 403 + 프론트 `safety.fun_layer` 이중 게이트, E2E 고정 |

## 6. 첫 주 실행 순서

1. D1~D6 확정 → 브랜치 분기 → 설계 문서 커밋.
2. 024 마이그레이션 + `archetype_engine.py` + 단위 테스트(백엔드).
3. 동시에 `index.html` 폰트·토큰 병합 + 트랙 타일 3개를 목 데이터로 렌더(프론트).
4. 금요일: `GET /routine/today` 확장 붙여 실제 데이터로 타일 동작 확인, CI 목록 보강 PR.
