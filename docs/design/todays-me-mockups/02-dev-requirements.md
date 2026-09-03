# 오늘의 나 — 개발 요건서 (4화면 통합 · 착수용)

작성 2026-09-03. 화면 기획서 4건(spec-01~04)과 교차 검수(01-cross-review)를 **개발 착수 단위**로 통합한 문서. 화면 기획서는 "무엇을 어떻게 보여주는가", 이 문서는 "무엇을 만들어야 하고 언제 끝난 것으로 보는가"를 정한다. 충돌 시 이 문서 → 01-cross-review → 브리프 → 화면 기획서 순으로 우선한다.

## 0. 기존 코드와의 접점 (착수 전 필독)

현재 루틴 제품(`bff/routine_routes.py`, `routine_repo.py`, `routine_engine.py`, `web/js/today.js`)은 **프로그램당 트랙 1개 + 하루 행동 카드 1개(+보조) 체크인** 구조다. "오늘의 나"가 요구하는 **하루 3트랙 일일 지표(물·걸음·마음챙김)**, 아키타입, 공유 카드는 아직 어떤 테이블·API에도 없다. 따라서 이 프로젝트는 기존 체크인을 대체하지 않고 **그 위에 일일 지표 레이어를 얹는다.**

| 기존 자산 | 재사용 방식 |
|---|---|
| `routine_checkin` (done/skip/na/undone, `applied_date`, E01 유예) | 행동 카드 체크인·주간 스트립·연속 일수의 **유일한 진실원천**. 손대지 않는다 |
| `GET /routine/today` 응답 | `tracks` · `archetype` · `safety` 블록을 **추가**한다(§4-1). 기존 키는 변경 금지 |
| `bff/app.py` `worst_band()` | 밴드 게이트의 입력. 경고/응급이면 재미 레이어 전체 차단 |
| `routine_engine.band_cap / banner_for` | 경고 밴드 치환 배너 재사용 |
| `analytics_events.EVENT_NAMES` | 신규 이벤트를 allowlist에 등록해야 `emit()`이 통과한다(§8) |
| `coaching_gamification.py` (points/level/badges) | **사용하지 않는다.** 정본 안티골(레벨·배지)과 충돌. 아키타입은 별도 모듈 |
| `web/js/today.js` `WeekDots` | 화면 1 주간 스트립으로 그대로 사용 |

**두 기준선 분리(C6)**: 주간 스트립 점·"N일째" = `routine_checkin` / 아키타입·링·화면 2 진입 = 신규 `daily_metrics` 완료 판정. 코드에서 두 값을 한 함수에서 섞어 계산하지 않는다.

## 1. 범위

| 포함 (v1) | 제외 (v1) |
|---|---|
| 화면 1 트랙 타일 3종과 입력 시트(컵 그리드·걸음 보정·1분 타이머) | 아키타입 7종 캐릭터 일러스트 6종(밸런스 수도승만 있음) → 디자인 후속 |
| 화면 2 오늘의 기록(링·지표 카드·환산·하이라이트) | 지표 카드 탭 → 주간 추이 시트(E8 결정 전까지 탭 비활성) |
| 화면 3 리빌(연출·태그·희귀도·7일 컬렉션) | 도감 전체 화면(v1은 7일 행 + 진입 링크만, 도감은 P1) |
| 화면 4 공유 카드(렌더·테마·스티커·코멘트·공유 3채널·자동 저장) | "이달의 나" 월간 카드(스키마 호환만 유지) |
| 웰니스 타입 5종: 온보딩 문진 4문항 배정, 설정 변경, 카드 라벨·기본 테마(§2-6) | 행동 패턴 기반 타입 재배정 제안(P2), 코치 말투 변형(P2) |
| 밴드 게이트, 희귀도 배치, 분석 이벤트 | 인스타 직접 공유(E3 결정 전까지 OS 공유시트로 대체) |

## 2. 기능 요구사항

우선순위: **P0** = 없으면 출시 불가, **P1** = 첫 릴리스 포함 목표, **P2** = 후속.

### 2-1. 공통·서버

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-C01 | 기록일은 로컬 00:00 경계. 23:50~00:10 입력은 정본 25 E01대로 전날 귀속. 서버 KST가 진실원천 | P0 | 23:55 입력·서버 00:03 도달 → `applied_date`=전날. 00:11 도달 → 당일 |
| FR-C02 | 취침 시각(`bedtime_at`)은 05:00 이전이면 전날 밤으로 귀속. 물·걸음·마음챙김에는 미적용 | P0 | 01:20 취침 → 전날 생활 리듬. 같은 시각 물 입력 → 당일 |
| FR-C03 | 트랙 완료 판정(잠정 A2): 물 ≥6컵 / 걸음 ≥6,000 또는 수동 확정 / 마음챙김 타이머 60초 완주 1회. 값은 서버 상수 1곳(`archetype_engine.GOALS`)에서만 읽는다 | P0 | 상수 변경만으로 판정이 바뀐다. 프론트에 목표값 하드코딩 없음 |
| FR-C04 | 아키타입은 완료 트랙 조합(brief §4 7종)으로만 결정. 0개면 `null`. `skip`·`na`·미입력은 조합에 들어가지 않는다 | P0 | 7조합 + 0 단위 테스트 통과 |
| FR-C05 | 밴드 게이트: `worst_band ∈ {경고, 응급}`이면 `tracks`는 유지하되 `archetype`·카드·컬렉션 API가 403 `band_gate`를 반환하고 화면 진입점이 렌더되지 않는다. 경고 밴드였던 날은 컬렉션에서도 제외 | P0 | 경고 밴드 계정으로 화면 2 CTA가 "이번 주 기록 보기"로 바뀌고, 리빌·카드 API 403 |
| FR-C06 | 희귀도: 월 단위 사용자 기준 분포(spec-03 §5-3). 분모 <100이면 `rarity_pct=null`. 배치 1일 1회(KST 04:00, 잠정) | P1 | 분모 99 → null, 100 → 정수 % |
| FR-C07 | 걸음 연동: 기록일 00:00~23:59 합산. `synced_at`이 30분 초과면 `stale=true`. 화면 진입 시 클라이언트가 1회 강제 동기화 | P0 | 31분 경과 응답에 `stale=true` |
| FR-C08 | 리빌 후 걸음 지연 유입으로 조합이 승격되면 00:10 마감 전까지 재계산. 이미 본 리빌을 자동 재표시하지 않고 화면 2 CTA에 점 표시 | P1 | 재계산 후 `archetype_id` 변경, `reveal_seen_at` 유지 |
| FR-C09 | 미완료 개수·결석 일수·타 사용자 비교값은 어떤 API 응답·이벤트 속성에도 싣지 않는다 | P0 | 응답 스키마 리뷰 체크리스트 통과 |

### 2-2. 화면 1 · 오늘의 체크인 (spec-01)

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-T1-01 | 기존 행동 카드·3버튼·되돌리기 5분·사유 태그는 현행 유지 | P0 | 기존 테스트 전부 통과 |
| FR-T1-02 | 물 타일: 탭 → 8칸 컵 그리드 시트, 컵 탭 +1, 길게 눌러 −1. 즉시 로컬 반영 후 `PUT /metrics/today` | P0 | 3컵 탭 → 응답 `water_cups=3`, 오프라인이면 큐잉 후 재전송 |
| FR-T1-03 | 걸음 타일: 자동 연동값 표시, "걸음 수 고치기"로 수동 보정(`source=manual`). 30분 초과 미동기화 시 "걸음은 조금 뒤에 들어와요" 캡션, 0으로 단정 금지 | P0 | 권한 거부 상태에서 "걸음 연결하기" 노출 |
| FR-T1-04 | 마음 타일: 1분 원형 타이머. 시작 즉시 깨어남, 60초 완주 시 완료. 중단 시 진행분 미저장 | P0 | 59초 중단 → `mind_seconds` 변화 없음 |
| FR-T1-05 | 캐릭터 잠듦/깨어남은 spec-01 §3-2 트리거표대로. 깨어남 ≠ 완료. 완료 뱃지는 목표 도달 시만 채움 | P0 | 물 1컵 → 깨어남·뱃지 테두리 / 6컵 → 뱃지 채움 |
| FR-T1-06 | 티저 문구는 완료·깨어남 트랙만 언급. 미완료 카운트("2개만 더") 금지 | P0 | 카피 표 §6 문구만 렌더 |
| FR-T1-07 | "오늘의 기록 보기"는 완료 트랙 ≥1일 때 활성. 비활성 탭도 이벤트 기록 | P0 | 0완료 → 비활성, 1완료 → 활성 |
| FR-T1-08 | 자정 롤오버 시 트랙 3종 잠듦 초기화, 앱 복귀 시 날짜 재검사 | P0 | 날짜 변경 후 포그라운드 → 새 `date_kst` 로드 |
| FR-T1-09 | 경고 밴드: 트랙 타일은 측정·기록형 문구로 유지, 티저·완료 뱃지·연속 일수 숨김 | P0 | spec-01 §3-4 치환표 |
| FR-T1-10 | 레이아웃: 트랙 타일까지 above the fold, 이후 스크롤, 하단 내비 고정 | P1 | 390×844에서 트랙 타일 하단 ≤ 780px |

### 2-3. 화면 2 · 오늘의 기록 (spec-02)

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-T2-01 | 세그먼트 링 3구간, 중앙 = 완료 트랙 수(0~3). 점수·퍼센트 금지 | P0 | 2완료 → 2구간 채움, 중앙 "2" |
| FR-T2-02 | 지표 카드 3종. 값 0·미측정은 회색 "–" + 캡션(A4). 빈 컵 그리드 금지(채운 컵만) | P0 | 걸음 null → "–" + "걸음 연결하기" |
| FR-T2-03 | 환산 문구는 spec-02 §5-2 구간표·계수(A1)로 서버가 생성해 `conversion_text`로 내려준다. 수량 0이면 문구 없음 | P0 | 6컵 → "= 작은 화분 3개", 1컵 → 문구 없음 |
| FR-T2-04 | 하이라이트 1줄: spec-02 §5-5 규칙(자기 기준 7일 최고치, 동률 제외, 트랙 순서 1개, 폴백 F1~F4) | P1 | 오늘 물 6 > 직전 최고 5 → 물 하이라이트 |
| FR-T2-05 | "N일째 이어졌어요"는 `routine_checkin` 연속 일수. 경고 밴드는 "오늘 기록이 남았어요"로 치환 | P0 | 두 값 출처가 다름을 테스트로 고정 |
| FR-T2-06 | CTA 변형: 완료≥1 → "오늘의 캐릭터 만나기" / 이미 본 날 → "캐릭터 다시 보기" / 0완료 → 화면 1 복귀 / 경고 밴드 → "이번 주 기록 보기" | P0 | 4변형 스냅샷 |
| FR-T2-07 | 과거 날짜 진입(캘린더)은 읽기 전용. 화면 체류 중 날짜가 바뀌어도 자동 전환하지 않고 "오늘로 이동" 버튼 | P1 | |

### 2-4. 화면 3 · 오늘의 캐릭터 (spec-03)

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-T3-01 | 사용자가 화면 2 CTA로만 연다. 자동 팝업·푸시·딥링크 직행 금지. 딥링크 잔존 경로는 밴드 확인 후 화면 2로 리다이렉트 | P0 | 딥링크 → 화면 2 |
| FR-T3-02 | 3단계 연출 총 ≤2,500ms(타임라인 spec-03 §4-1), 탭으로 건너뛰기, `prefers-reduced-motion`이면 페이드만. 햅틱 1회, 사운드 기본 꺼짐 | P0 | 연출 총시간 측정 ≤2,500ms |
| FR-T3-03 | 같은 날 재진입은 연출 생략, 결과만 표시(`reveal_seen_at` 기준) | P0 | 2회차 진입 애니메이션 없음 |
| FR-T3-04 | "왜 이 캐릭터?" 태그 ≤3, 완료 트랙만, 템플릿 spec-03 §7-3 | P0 | 2완료 → 태그 2개 |
| FR-T3-05 | 희귀도 줄: `rarity_pct` null이면 줄 자체 숨김(대체 문구 없음). 우열·등급·순위 어휘 금지 | P1 | null → DOM 미렌더 |
| FR-T3-06 | 지난 7일 컬렉션: 아키타입 받은 날만 슬롯, 빈 슬롯·고스트 없음, 오늘은 검정 원 최우측. 슬롯 1개면 캡션 | P1 | 3일 받음 → 슬롯 3개 |
| FR-T3-07 | 닫기·"오늘은 여기까지" 이탈 시 확인 다이얼로그·죄책감 문구 없음 | P0 | |
| FR-T3-08 | 7종 아키타입 사전(EN·KO·로어·배경색·글리프)은 서버 상수. 클라이언트는 `archetype_id`만 받아 로컬 사전으로 렌더 | P0 | 사전 키 7개 일치 테스트 |

### 2-5. 화면 4 · 공유 카드 (spec-04)

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-T4-01 | 카드 페이로드는 화이트리스트 열거형으로만 생성(spec-04 §4-2). 렌더러는 미지 키가 있으면 렌더 거부 | P0 | `systolic_bp` 주입 → 예외, PNG 미생성 |
| FR-T4-02 | 건강 수치·밴드·구간·연속 끊김·미완료·순위·이름·프로필 사진은 카드에 절대 미노출 | P0 | 골든 이미지 + 키 이름 금지어 검사 |
| FR-T4-03 | 포맷 2종 9:16(1080×1920)·1:1(1080×1080), 픽셀 스펙 spec-04 §3. 부분 완료 시 지표 줄 수 1~3 변형 | P0 | 7아키타입×3테마×2포맷×3줄수 골든 스냅샷 |
| FR-T4-04 | 숫자 숨기기: ON이면 `metrics`·`rarity_pct`를 페이로드에서 제거. 기본 OFF, v1 로컬 저장 | P0 | ON 렌더에 숫자 0개 |
| FR-T4-05 | 테마 3종(coral #E2593A / lavender / forest), 스티커 ≤6·종류별 ≤3, 코멘트 ≤20자 필터 | P1 | 21자 → 422 |
| FR-T4-06 | 카드는 화면 4 진입 시 1차 자동 저장, 편집은 800ms 디바운스 갱신. 재편집 창 = 기록일 당일 00:10. 이후 불변·읽기 전용. 재생성 없음 | P0 | 00:11 PATCH → 409 `locked` |
| FR-T4-07 | 공유 채널: 이미지 저장(P0), 카카오톡 1:1 자동 렌더(P1), 인스타 스토리 직접 공유(E3 결정 시, 그 전엔 OS 공유시트). 모든 실패는 "이미지 저장" 폴백 바텀시트 | P0/P1 | 미설치 감지 → 폴백 시트 |
| FR-T4-08 | 서버 렌더(폰트 임베드) 권장. 미확보 시 클라 렌더 + 화이트리스트 복제(E4) | P1 | |

### 2-6. 웰니스 타입 5종 (브리프 §4-2·§4-3 · 교차검수 C12 B안)

| ID | 요구사항 | 우선 | 수용 기준 |
|---|---|---|---|
| FR-C10 | 타입 사전 5종은 서버 상수(`wellness_type.TYPES`: id, name_ko, name_en, one_liner, default_theme). 클라이언트는 `type_id`만 받는다 | P0 | 사전 키 5개 일치 테스트 |
| FR-C11 | 온보딩 문진 4문항×5지선다. 최다 득표 타입 배정, 동점이면 Q4 답 우선. 결과는 `wellness_type` 테이블에 `assigned_by=onboarding`으로 저장 | P0 | (Q1 야망가, Q2 신생아, Q3 야망가, Q4 신생아) → 동점 → 신생아 |
| FR-C12 | 설정에서 5종 중 직접 변경 가능(`assigned_by=user`). 변경 즉시 카드 기본 테마·라벨에 반영. 우열·추천 문구 없음 | P0 | 변경 후 `GET /wellness-type` 반영 |
| FR-C13 | 타입은 밴드와 무관하게 유지. 단 타입 카드·공유 카드는 경고·응급 밴드에서 숨김(FR-C05와 동일 게이트) | P0 | 경고 밴드: `GET /wellness-type` 200, `POST /card/type` 403 |
| FR-C14 | 온보딩 직후 "타입 카드"(1:1) 생성·공유. 카드 렌더 파이프라인과 화이트리스트 공유, `metrics=[]` | P1 | 골든 이미지 5종 |
| FR-C15 | 문진 문항·선택지·결과 카피는 브리프 §4-3 그대로. 선택지 12자 이내, 의료 어휘·"분석 결과"류 단정 금지 | P0 | 카피 lint 통과 |

## 3. 데이터 모델 (신규 5테이블, 기존 테이블 무변경)

```sql
-- 하루 3트랙 지표. subject×date 1행. 기존 routine_checkin과 독립.
CREATE TABLE IF NOT EXISTS daily_metrics (
  subject_id      TEXT NOT NULL,
  metric_date     TEXT NOT NULL,          -- applied_date(KST, E01 적용)
  water_cups      INTEGER DEFAULT 0,      -- 0~8
  steps           INTEGER,                -- NULL=미측정
  steps_source    TEXT DEFAULT 'none',    -- auto | manual | none
  steps_synced_at TEXT,
  steps_confirmed INTEGER DEFAULT 0,      -- 수동 확정
  mind_seconds    INTEGER DEFAULT 0,      -- 완주 세션 합
  mind_sessions   INTEGER DEFAULT 0,      -- 60초 완주 횟수
  bedtime_at      TEXT,                   -- 05:00 이전은 전날로 귀속된 값
  band_snapshot   TEXT,                   -- 그날의 worst_band(컬렉션 제외 판정용)
  created_at TEXT, updated_at TEXT,
  PRIMARY KEY (subject_id, metric_date));

-- 아키타입 결과. 완료 트랙 조합이 바뀌면 같은 행을 갱신(00:10까지).
CREATE TABLE IF NOT EXISTS archetype_result (
  subject_id       TEXT NOT NULL,
  metric_date      TEXT NOT NULL,
  archetype_id     TEXT NOT NULL,         -- 7종 enum
  completed_tracks TEXT NOT NULL,         -- JSON ["diet","exercise","habit"]
  rarity_pct       INTEGER,               -- NULL=표본 미달·미집계
  reveal_seen_at   TEXT,
  created_at TEXT, updated_at TEXT,
  PRIMARY KEY (subject_id, metric_date));

-- 공유 카드(=도감 레코드). subject×date 1장. locked_at 이후 불변.
CREATE TABLE IF NOT EXISTS share_card (
  card_id          TEXT PRIMARY KEY,
  subject_id       TEXT NOT NULL,
  metric_date      TEXT NOT NULL,
  archetype_id     TEXT NOT NULL,
  theme_id         TEXT DEFAULT 'coral',  -- coral | lavender | forest
  stickers_json    TEXT DEFAULT '[]',     -- [{type,x,y,scale,rot}] ≤6
  comment          TEXT,                  -- ≤20자, 필터 통과분
  hide_numbers     INTEGER DEFAULT 0,
  metrics_snapshot TEXT NOT NULL,         -- 화이트리스트 통과 JSON
  rarity_pct       INTEGER,
  locked_at        TEXT,                  -- metric_date 다음날 00:10
  created_at TEXT, updated_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_share_card_day ON share_card (subject_id, metric_date);

-- 웰니스 타입(성향 층). subject 1행, 변경 이력은 assigned_at 갱신으로만.
CREATE TABLE IF NOT EXISTS wellness_type (
  subject_id    TEXT PRIMARY KEY,
  type_id       TEXT NOT NULL,            -- 5종 enum (브리프 §4-2)
  assigned_by   TEXT NOT NULL,            -- onboarding | user | suggestion(P2)
  quiz_answers  TEXT,                     -- JSON [q1..q4] 선택 index, 재배정 참고용
  assigned_at   TEXT, updated_at TEXT);

-- 월간 희귀도 배치 결과
CREATE TABLE IF NOT EXISTS archetype_monthly_stat (
  month         TEXT NOT NULL,            -- YYYY-MM
  archetype_id  TEXT NOT NULL,
  user_count    INTEGER NOT NULL,         -- N
  denominator   INTEGER NOT NULL,         -- D (리빌 1회 이상 사용자)
  computed_at   TEXT,
  PRIMARY KEY (month, archetype_id));
```

`completed_tracks` 산출(서버, `archetype_engine.py` 신규):

```
diet     = water_cups >= GOALS.water_cups(6)
exercise = (steps is not None and steps >= GOALS.steps(6000)) or steps_confirmed
habit    = mind_sessions >= 1
archetype_id = COMBO[frozenset(완료 트랙)]  # 0개 → None
```

## 4. API 계약 (BFF, `bff/metrics_routes.py` 신규 + `routine_routes.py` 확장)

모든 엔드포인트는 기존 인증·`subject_id` 해석과 `personal_info_consent_required`(403) 규칙을 따른다. 날짜는 서버 KST 확정값을 `applied_date`로 돌려준다.

### 4-1. `GET /routine/today` 확장 (기존 키 유지, 3블록 추가)

```json
{
  "...기존 키...": "...",
  "date_kst": "2026-09-02",
  "safety": { "band": "안정", "fun_layer": true },
  "tracks": {
    "water": { "cups": 4, "goal": 6, "awake": true, "complete": false },
    "steps": { "value": 3120, "goal": 6000, "source": "auto", "synced_at": "2026-09-02T18:02:00+09:00", "stale": false, "permission": "granted", "awake": true, "complete": false },
    "mind":  { "seconds": 0, "sessions": 0, "awake": false, "complete": false }
  },
  "archetype": { "preview": null, "completed_count": 0, "seen_today": false }
}
```

- `safety.fun_layer=false`(경고·응급)면 `archetype`은 `null`, 클라이언트는 티저·뱃지·연속 일수를 렌더하지 않는다.
- `awake`·`complete`는 서버 파생값. 프론트 자체 판정 금지(spec-01 §5-1).

### 4-2. 일일 지표

| 메서드 | 경로 | 요청 | 응답 | 오류 |
|---|---|---|---|---|
| `PUT` | `/metrics/today` | `{ "water_cups": 4 }` 또는 `{ "steps": 6400, "source": "manual", "confirmed": true }` 또는 `{ "mind_session_completed": true }` 또는 `{ "bedtime_at": "..." }`, 공통 `client_ts`, `idempotency_key` | `{ ok, applied_date, tracks, archetype }` (4-1과 동일 블록) | 400 `invalid_value`(컵 0~8 외, 걸음 <0), 409 `date_locked`(applied_date가 어제이고 00:10 경과) |
| `POST` | `/metrics/steps/sync` | `{ "steps": 5120, "synced_at": "..." }` (헬스 SDK 값 전달) | 동일 | 걸음 `source=manual·confirmed`면 자동값이 덮어쓰지 않음 |
| `GET` | `/metrics/day?date=YYYY-MM-DD` | — | 화면 2 페이로드(§4-3) | 404 `no_record` |

### 4-3. 화면 2 페이로드 `GET /metrics/day`

```json
{
  "date": "2026-09-02", "is_today": true, "is_past": false,
  "band": "안정", "fun_layer": true,
  "completed_count": 3,
  "tracks": { "diet": "done", "exercise": "done", "habit": "done" },
  "metrics": [
    { "kind": "water_cups", "value": 6, "unit_label": "컵의 물", "conversion_text": "= 작은 화분 3개" },
    { "kind": "steps", "value": 6400, "unit_label": "걸음", "conversion_text": "= 한강 다리 2개", "stale": false },
    { "kind": "mindful_min", "value": 7, "unit_label": "분", "conversion_text": "= 노래 2곡" }
  ],
  "highlight": { "type": "water", "text": "이번 주 물을 가장 많이 마신 날" },
  "streak_text": "5일째 이어졌어요",
  "cta": "reveal"   // reveal | reveal_replay | go_today | weekly_report
}
```

`conversion_text`·`highlight.text`·`streak_text`는 **서버가 최종 문자열로** 내려 프론트에 카피 규칙이 분산되지 않게 한다. 경고 밴드는 `streak_text="오늘 기록이 남았어요"`, `cta="weekly_report"`.

### 4-4. 아키타입·리빌

| 메서드 | 경로 | 응답 | 오류 |
|---|---|---|---|
| `GET` | `/archetype/day?date=` | `{ date, archetype_id, name_en, name_ko, lore, elements[], tags[≤3], rarity_pct, seen_today, collection_last7:[{date, archetype_id, is_today}] }` | 403 `band_gate`, 404 `no_archetype`(0완료) |
| `POST` | `/archetype/seen` | `{ ok, reveal_seen_at }` | |
| `GET` | `/archetype/collection?from=&to=` (P1 도감) | `[{date, archetype_id}]`, 7종 중 만난 종 수만 | 미실천 일수·달성률 없음 |

응답에 밴드 라벨·구간·검진 수치·연속 일수·총 실천일을 싣지 않는다(spec-03 §5-1 금지 필드). API 스키마 테스트로 고정.

### 4-5. 공유 카드

| 메서드 | 경로 | 요청/응답 | 오류 |
|---|---|---|---|
| `POST` | `/card` | `{ date }` → `{ card_id, payload(화이트리스트), locked_at }` (이미 있으면 기존 반환) | 403 `band_gate`, 404 `no_archetype` |
| `PATCH` | `/card/{card_id}` | `{ theme_id?, stickers?, comment?, hide_numbers? }` → 갱신 페이로드 | 409 `locked`, 422 `comment_too_long`·`sticker_limit`·`comment_filtered` |
| `GET` | `/card/{card_id}/render?format=story\|feed` | `image/png` | 500 `render_rejected`(미지 키) |
| `GET` | `/card/list?month=` (P1 도감) | `[{card_id, date, archetype_id, theme_id}]` | |

`CardPayload` 허용 키: `date_label, brand_label, metrics[], archetype_en, archetype_ko, archetype_lore, rarity_pct, theme_id, stickers[], comment, hide_numbers, wellness_type_label`. 그 외 키 존재 시 렌더 거부. `wellness_type_label`은 서버 상수 5종 라벨(≤13자) 중 하나만 허용.

### 4-6. 웰니스 타입

| 메서드 | 경로 | 요청/응답 | 오류 |
|---|---|---|---|
| `GET` | `/wellness-type/quiz` | → `{ questions:[{id, text, options:[{index, label, type_id}]}] }` (브리프 §4-3 상수) | |
| `POST` | `/wellness-type/quiz` | `{ answers:[i1,i2,i3,i4] }` → `{ type_id, name_ko, one_liner, default_theme, assigned_at }` | 400 `invalid_answers` |
| `GET` | `/wellness-type` | → 동일 객체 (미배정이면 `type_id=null`) | |
| `PUT` | `/wellness-type` | `{ type_id }` → 동일 객체, `assigned_by=user` | 400 `unknown_type` |
| `POST` | `/card/type` (P1) | `{}` → 타입 카드 `{ card_id, payload }` (`metrics=[]`, `archetype_*` 대신 타입 일러스트·라벨) | 403 `band_gate`, 404 `no_type` |

카드 생성(`POST /card`) 시 서버가 `wellness_type_label`과 기본 `theme_id`를 타입 사전에서 채운다. 타입 미배정이면 라벨 생략, 테마 coral.

## 5. 서버 계산 규칙 요약 (단위 테스트 대상)

| 규칙 | 정의 | 출처 |
|---|---|---|
| 기록일 | KST 00:00 경계. `client_ts` 23:50~23:59:59 & 서버 00:00~00:10 → 전날 | 정본 25 E01, C1 |
| 취침 귀속 | `bedtime_at` 시각 < 05:00 → 전날 밤 | C1 |
| 완료 판정 | 물 ≥6 / 걸음 ≥6,000 또는 confirmed / 마음 세션 ≥1 | A2 (E1 대기) |
| 깨어남 | 물 ≥1 / 걸음 ≥1,000 또는 manual / 타이머 시작 | spec-01 §3-2 |
| 아키타입 | 완료 조합 7종, 0개 null | brief §4 |
| 환산 | 화분 = floor(컵/2), 다리 = floor(걸음/3000), 노래 = floor(분/3.5) 상한 8, 0이면 문구 없음 | A1 |
| 하이라이트 | 오늘 > max(직전 6일), 동률 제외, 트랙 순서 1개, 폴백 F1~F4 | spec-02 §5-5 |
| 희귀도 | N/D×100 반올림, 사용자 단위, D<100 → null, 1% 미만 별도 문구 | spec-03 §5-3 |
| 카드 잠금 | `locked_at = metric_date+1일 00:10` | C5 |
| 타입 배정 | 4문항 최다 득표, 동점 시 Q4 | brief §4-3 |
| 걸음 지연 | now − synced_at > 30분 → stale | C2 |

## 6. 밴드 게이팅 매트릭스

| 요소 | 안정 | 주의 | 경고·응급 |
|---|---|---|---|
| 트랙 타일·지표 입력 | 표시 | 표시 | 표시(측정·기록형 문구) |
| 완료 뱃지·깨어남 연출 | 표시 | 표시 | 숨김 |
| 아키타입 티저·리빌·카드·컬렉션 | 표시 | 표시 | **숨김 + API 403** |
| 웰니스 타입(프로필·설정) | 표시 | 표시 | 표시(타입 카드만 숨김) |
| "N일째 이어졌어요" | 표시 | 표시 | "오늘 기록이 남았어요" |
| 하이라이트 1줄 | 표시 | 표시 | 표시 (E7 확인 중) |
| 화면 2 CTA | 캐릭터 만나기 | 캐릭터 만나기 | 이번 주 기록 보기 |
| 안전 배너 | 없음 | "진료와 병행하세요" 상시 | 진료 우선 배너 최상단 고정 |

## 7. 비기능 요구사항

| 항목 | 기준 |
|---|---|
| 리빌 연출 | ≤2,500ms, 건너뛰기 즉시, reduced-motion 대응 |
| 카드 렌더 | 서버 P95 ≤3s, PNG ≤2MB, 폰트 임베드(Lexend·Jua·Gowun Dodum) |
| 오프라인 | 지표 입력은 로컬 큐 + `idempotency_key`로 재전송. 리빌·카드는 온라인 전용(오프라인 배너) |
| 접근성 | 탭 영역 ≥44px, 폰트 200%에서 버튼 미절단, 색 외 구분(체크 아이콘), aria-live 문구는 각 spec §8 |
| 개인정보 | 카드에 이름·프로필 사진 미노출, 코멘트 원문·카드 이미지는 이벤트에 미수집 |
| 컴플라이언스 | 정본 §0-2 금칙 6종을 카피 lint(`compliance_check`)로 CI에서 검사 |

## 8. 분석 이벤트 (신규 등록 · `analytics_events.EVENT_NAMES`)

속성은 라벨·카운트·불리언만. 밴드·검진 수치·미완료 개수·타인 비교값 금지.

| 화면 | 이벤트 |
|---|---|
| 1 | `tracker_view`, `track_input`, `track_wake`, `track_complete`, `archetype_teaser_view`, `stats_cta_tap`, `steps_sync_delay`, `d1_celebration_view` (기존 `coaching_checkin`은 유지) |
| 2 | `stats_view`, `stats_ring_animation_complete`, `stats_metric_card_tap`, `stats_conversion_copy_shown`, `stats_highlight_shown`, `stats_steps_unavailable`, `stats_steps_connect_tap`, `stats_empty_view`, `stats_exit` |
| 3 | `reveal_opened`, `reveal_animation_completed`, `reveal_animation_skipped`, `reveal_rarity_shown`, `reveal_card_cta_tapped`, `reveal_dismissed`, `reveal_collection_slot_tapped`, `reveal_collection_opened`, `reveal_error_shown`, `reveal_blocked_by_band` |
| 타입 | `wellness_quiz_start`, `wellness_quiz_complete(type_id)`, `wellness_type_change(from,to)`, `type_card_share_click(channel)` |
| 4 | `card_view`, `card_format_change`, `card_hide_numbers_toggle`, `card_theme_select`, `card_sticker_add/remove/move`, `card_comment_submit`, `card_share_click`, `card_share_result`, `card_saved_to_dex`, `card_render_error` |

속성 정의는 각 화면 기획서 §9(§11·§16)를 그대로 쓴다.

## 9. 작업 분해 (착수 순서)

| # | 작업 | 담당 | 선행 | 산출 |
|---|---|---|---|---|
| B1 | `daily_metrics`·`archetype_result` 테이블, `archetype_engine.py`(완료 판정·조합·환산·하이라이트·E01/취침 귀속), 단위 테스트 | BE | — | §3·§5 |
| B2 | `PUT /metrics/today`, `POST /metrics/steps/sync`, `GET /metrics/day`, `/routine/today` 3블록 확장, 밴드 게이트 | BE | B1 | §4-1~4-3 |
| B3 | `GET /archetype/day`, `POST /archetype/seen`, 7종 사전 상수, 금지 필드 스키마 테스트 | BE | B1 | §4-4 |
| B4 | `share_card` 테이블, `build_card_payload`·`render_card`(화이트리스트·fail-closed), `POST/PATCH /card`, `/render`, 잠금 | BE | B3, E4 | §4-5 |
| B5 | 희귀도 배치(`archetype_monthly_stat`), `EVENT_NAMES` 등록 | BE | B3 | §5·§8 |
| F1 | 화면 1: 트랙 타일 3종 + 컵 그리드·걸음 보정·1분 타이머 시트, 티저, CTA 활성 로직, 오프라인 큐 | FE | B2 | spec-01 |
| F2 | 화면 2: 링·지표 카드·환산·하이라이트·CTA 4변형·과거 날짜 읽기 전용 | FE | B2 | spec-02 |
| F3 | 화면 3: 연출 타임라인·건너뛰기·태그·희귀도·7일 컬렉션·재진입 | FE | B3 | spec-03 |
| F4 | 화면 4: 포맷 토글·숫자 숨기기·테마·스티커·코멘트·공유 3채널 폴백·자동 저장 | FE | B4 | spec-04 |
| B6 | `wellness_type` 테이블, 타입·문진 상수, `/wellness-type/*`, 카드 페이로드 `wellness_type_label`·기본 테마 주입, `/card/type`(P1) | BE | B4 | §2-6·§4-6 |
| F5 | 온보딩 문진 4문항 화면 + 결과 화면 + 타입 카드 공유(P1), 설정 "내 웰니스 타입" 변경, 카드 하단 라벨 | FE | B6 | 브리프 §4-3, spec-04 §18 |
| D1 | 아키타입 6종 일러스트(spec-03 §6-1 설정표), 7종 슬롯 글리프, 카드 골든 이미지 | 디자인 | — | SVG |
| D3 | 웰니스 타입 5종 일러스트(03-archetype-image-prompts.md), 온보딩 결과·타입 카드 레이아웃 | 디자인 | — | PNG/SVG |
| D2 | 신규 배경 토큰 #FFC98F·#E4EBC7 대비 실측, 카드 테마 lavender/forest 색 확정 | 디자인 | — | 브리프 §6 |
| Q1 | 카피 lint(금칙 6종·글자수 예산) CI, 카드 금지 키 주입 테스트, 밴드 게이트 E2E | QA | B2~B4 | §7 |

병렬 가능: B1→(B2·B3) 동시, D1·D2는 처음부터. F1·F2는 B2 목 서버로 선행 가능.

## 10. 결정 대기 항목과 착수 기본값

착수를 막지 않도록 **기본값으로 진행**하고, 결정이 바뀌면 상수·플래그만 바꾼다.

| # | 결정 | 착수 기본값 | 바뀔 때 손대는 곳 |
|---|---|---|---|
| E1 | 트랙별 완료 목표치 | 물 6 / 걸음 6,000 / 마음 1세션 | `archetype_engine.GOALS` 1곳 |
| E2 | 한강 다리 비유 | 유지 | 환산 사전 1행 |
| E3 | 인스타 직접 공유 Meta 앱 ID | OS 공유시트로 대체 | 화면 4 T4-40 핸들러 |
| E4 | 서버 렌더 인프라 | 서버 렌더(headless) 전제, 없으면 클라 렌더 + 화이트리스트 복제 | B4 렌더 모듈 |
| E5 | 카카오 이미지 호스팅 | 24h 서명 URL | B4 업로드 어댑터 |
| E6 | 정본 버튼 13자 | "루틴 시작하기" | 정본 27 §3-5 |
| E7 | 경고 밴드 하이라이트 유지 | 유지 | 게이팅 매트릭스 1칸 |
| E8 | 지표 카드 탭 주간 추이 | 탭 비활성 | F2 |
