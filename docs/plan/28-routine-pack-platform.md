# 28 — 루틴 팩 플랫폼: 계획과 핵심 요건 (v1.0 — 구현 완료)

> 목적: "골프 6개월 코스", "일본어 6개월 루틴"처럼 **타당한 루틴을 만들어 꽂아 넣을 수 있는 구조**로 전환한다. 현재 루틴 엔진은 건강 12주 커리큘럼 1개가 코드에 박혀 있다.
> 상태: **승인(2026-09-04, D1~D9 권고안 그대로) → Phase 0~3 구현 완료(2026-09-29).** 구현 중 달라진 점은 §12. 브랜치 `feat/routine-pack-platform`.
> 정본 관계: 이 문서는 [25-routine-transition-spec](25-routine-transition-spec.md)·[27-routine-content](27-routine-content.md)를 **대체하지 않는다.** 건강 12주 커리큘럼의 내용 정본은 27 그대로이고, 이 문서는 그 커리큘럼을 "팩 1호"로 옮겨 담는 **그릇(플랫폼)** 의 정본이다.
> 작성: 2026-09-04 · 브랜치 `feat/routine-packs`

---

## 0. 한 줄 결론

루틴을 **"팩(pack)"이라는 선언적 데이터 파일**로 정의하고, 엔진·저장소·API·화면은 팩을 읽어서 동작하게 바꾼다. 건강 12주 커리큘럼은 코드에서 뽑아 `health_12w` 팩으로 만들되 **동작이 1바이트도 바뀌지 않음을 골든 테스트로 증명**한다. 새 루틴 추가는 "팩 파일 1개 + lint 통과 + PR" 이 전부가 되게 한다. 안전 규칙(응급 중단·경고 밴드 캡·효능표방 차단·무비난 카피)은 팩이 끌 수 없는 플랫폼 불변식으로 남긴다.

---

## 1. 현황 진단 — 무엇이 어디에 박혀 있나

| 층 | 파일 | 하드코딩된 것 | 플랫폼화 시 영향 |
|---|---|---|---|
| 커리큘럼 | `routine_engine.py` | `WEEKS`(12주 메타), `ROUTINE_ACTIONS`(주차×트랙 36개), `ASK_CHIPS`, `_BANNER`, `PHASES`(2/4/4/2), `TRACKS`(diet/exercise/habit), `FOCUS_TRACK`, 입력 위젯 상수 | 전부 팩 데이터로 이동. 엔진은 팩을 받아 계산하는 순수 함수만 남김 |
| 문진·보조 KB | `coaching_engine.py` | `INTAKE_QUESTIONS`(트랙별 3문항), `KB`(보조 행동 19개), `_select_keys`(문자열 리터럴 매칭), `_BANNER`, `_TRACK_NOUN` | 팩이 자체 문진·보조 풀·선택 규칙을 가진다. 기존 3트랙은 `health_12w` 팩에 그대로 이식 |
| 컴플라 | `coaching_compliance.py` | 효능표방·처방성 정규식(의료 전용) | 유지. 팩의 `safety_profile`에 따라 추가 금칙 세트를 얹는 구조로 확장 |
| 저장소 | `routine_repo.py` | `week_of()` 의 `min(12, …)`, `build_week_state()` 의 `range(1, 13)`, `create_program()` 의 `weeks_total=12` | `program.weeks_total`·`pack_id` 로 일반화 |
| 라우트 | `bff/routine_routes.py` | `weeks_total: 12`, 리포트 `min(12, wk+1)`, `unknown_track` 검사가 `eng.TRACKS` 고정, 보조 풀이 `rag_db.coaching_plan`에 결합, `/diagnosis` 추천이 3트랙 고정 | `pack_id` 를 받는 시작 API, 팩 카탈로그 API 신설. 보조 풀은 팩에서 직접 |
| 프론트 | `program.js` `today.js` `onboard.js` `health.js` `ui.js` | "12주"·`/ 12`·`clamp(…,1,12)` 18곳, `PHASE()` 주차 경계 함수, 트랙 카드 3개 리터럴(이모지·이름·설명), `track: 'diet'` 기본값 | 전부 서버 페이로드(`program.weeks_total`, `program.phases`, `pack.tracks`)에서 받도록 |
| 이벤트 | `analytics_events.py` | `track` 라벨 주석이 3트랙 전제 | `pack_id` 라벨 추가 |
| 테스트 | `tests/test_routine.py`(22) `test_coaching_engine.py`(11) | 12주·3트랙 가정 | 골든 테스트로 승격 + 팩별 파라미터화 테스트 신설 |
| 재미 레이어 | `archetype_engine.py` `metrics_routes.py` | 물·걸음·마음 3지표는 **루틴 프로그램과 독립**(별도 테이블) | 이번 범위 밖. 팩과 결합하지 않는다(§8 E2) |

결론: 콘텐츠와 엔진이 같은 파일에 있어서 새 루틴 하나를 넣으려면 파이썬 6곳·JS 5곳을 고쳐야 한다. 이것이 플랫폼화의 대상이다.

---

## 2. 목표와 비목표

### 2-1. 목표

| # | 목표 | 성공 기준 |
|---|---|---|
| G1 | 새 루틴 추가 = 팩 파일 1개 | 코드 변경 0줄로 "일본어 6개월" 팩이 온보딩·홈·리포트에 뜬다 |
| G2 | 기존 건강 12주 무회귀 | `health_12w` 팩 적용 전후 `GET /routine/today`·`/week-report` 페이로드가 전 주차×트랙×밴드에서 동일(골든 테스트) |
| G3 | 안전 불변식은 팩이 못 끈다 | 응급 전면 중단, 경고 밴드 캡, WC-C 스캔, 무비난 카피 규칙이 팩 설정과 무관하게 서버에서 강제 |
| G4 | 타당성은 lint 로 기계 검증 | 글자수 예산·금칙·출처 필수·주차 수 일치·id 유일성·입력 위젯 유효성이 CI 에서 실패로 잡힌다 |
| G5 | 기간·단계 자유 | 4~52주, 단계(phase) 개수·경계·이름을 팩이 정의 |
| G6 | 작성 워크플로 정착 | 스캐폴드 → (선택) LLM 초안 → lint → 리뷰 → PR 의 순서가 문서·스크립트로 고정 |

### 2-2. 비목표 (이번에 하지 않음)

- 관리자 웹 UI에서 팩을 편집·배포하는 CMS. v1은 **레포 안의 파일 + PR 리뷰**가 편집기다(D1).
- 재미 레이어(아키타입·공유 카드)를 팩별로 커스터마이즈하는 것.
- 서버 푸시 알림, 유료 코스, 팩 마켓플레이스.
- LLM 이 런타임에 행동 문구를 생성하는 것. 팩은 **결정적 템플릿**이어야 한다(25 §C6 원칙 유지).

---

## 3. 목표 아키텍처

```
routines/packs/
  health_12w/pack.json          ← 팩 1호: 지금 코드의 12주 건강 커리큘럼(내용 정본 = 27)
  golf_6m/pack.json             ← 샘플 2호(26주, physical)
  japanese_6m/pack.json         ← 샘플 3호(26주, neutral)
  _schema/pack.schema.json      ← JSON Schema(버전 1)

routine_packs.py                ← 팩 로더·레지스트리·검증(pydantic). import 시 전 팩 로드+검증
routine_engine.py               ← 팩을 인자로 받는 순수 함수만 남김(week_meta/today_action/band_cap/transition…)
routine_repo.py                 ← weeks_total·pack_id 기반. 12 리터럴 제거
bff/routine_routes.py           ← GET /routine/packs, POST /routine/start{pack_id,track}, 페이로드에 pack 블록
coaching_compliance.py          ← 프로필별 금칙 세트 추가(medical/physical/neutral)
scripts/pack_lint.py            ← G4 검사기. CI 에서 실행
scripts/pack_new.py             ← 스캐폴드(주차 수·트랙 수·프로필을 인자로 빈 팩 생성)
scripts/pack_draft.py           ← (선택, D8) 브리프 → 팩 초안 생성. 결과는 반드시 lint+리뷰
web/js/*                        ← 주차 수·단계·트랙 카드를 페이로드에서 렌더
```

### 3-1. 데이터 흐름

1. 서버 기동 시 `routine_packs.load_all()` 이 `routines/packs/*/pack.json` 을 읽어 검증한다. 하나라도 스키마 위반이면 **기동 실패**(잘못된 팩이 조용히 서빙되는 일이 없게).
2. 온보딩은 `GET /routine/packs` 로 카탈로그(팩 id·이름·기간·프로필·트랙 카드·추천 여부)를 받는다.
3. `POST /routine/start {pack_id, track, intake}` 가 프로그램을 만든다. `routine_program` 에 `pack_id`·`pack_version`·`weeks_total`·`phases_json` 을 저장한다.
4. `GET /routine/today` 는 프로그램의 `pack_id` 로 팩을 찾아 오늘 행동·주간 미션·질문칩·배너를 만든다. 페이로드에 `pack {id, name, weeks_total, phases[]}` 블록이 추가된다.
5. 프로그램 생성 시점의 `pack_version` 을 고정한다. 팩을 고쳐 배포해도 진행 중 프로그램은 옛 버전으로 계속 간다(팩 파일에 과거 버전을 같이 두거나, 프로그램에 스냅샷을 저장 — D1 결정에 종속).

### 3-2. 안전 프로필 (플랫폼 불변식과 팩 재량의 경계)

| 규칙 | medical (건강) | physical (골프·운동류) | neutral (어학·취미) | 팩이 바꿀 수 있나 |
|---|---|---|---|---|
| 응급 밴드 → 루틴 전면 중단(S9) | 적용 | 적용 | 적용 | **불가** |
| 경고 밴드 → 보조 행동 캡 0 | 적용 | 적용 | 미적용 | 불가 |
| 경고 밴드 배너 | 진료 우선 배너 고정 | 운동 전 의료진 상담(clearance) 배너 고정 | 없음 | 문구만 팩 재량, 노출 여부는 불가 |
| 주의 밴드 → 캡 1·"진료와 병행" 배너 | 적용 | 적용 | 미적용 | 불가 |
| 경고 밴드 → 주차 advance 금지 | 적용 | 적용 | 미적용 | 불가 |
| WC-C1 효능표방·WC-C2 처방성 스캔 | 적용 | 적용 | 적용(건강 결과 약속은 어떤 팩도 금지) | 불가 |
| 도메인 금칙 세트 | 27 §0-2 | + 부상·통증 관련 처방("무릎 아프면 …하세요") 금지 | + 학습 성과 보장("6개월이면 N3 합격") 금지 | 세트 추가만 가능, 제거 불가 |
| 무비난·안티골(랭킹·미완료 카운트·붉은색·전면 축하) | 적용 | 적용 | 적용 | 불가 |
| 출처(cite) 필수 | 공신력 보건 출처 | 공식 교습 지침·협회 자료 | 공식 시험 요강·교재 | 출처 종류만 프로필별로 다름, 필수 여부는 불가 |
| 글자수 예산(행동 30자·캡션 20자·버튼 12자·칩 24자) | 적용 | 적용 | 적용 | 불가 |

밴드는 건강 페르소나에서 나온다. 비의료 팩을 하는 사용자도 페르소나가 응급이면 앱 전체가 멈춘다(지금과 동일). 이것이 "안전 게이트는 공유"(18 §0) 원칙의 팩 버전이다.

---

## 4. 팩 정의 포맷 (핵심 요건)

### 4-1. 최상위 구조

```jsonc
{
  "schema_version": 1,
  "id": "japanese_6m",              // [a-z0-9_]+, 유일
  "version": 1,                     // 내용 바뀌면 +1
  "name": "일본어 6개월 루틴",        // 20자 이내
  "tagline": "하루 10분, 26주 뒤 N5 문장이 읽혀요",   // 30자 이내, 성과 보장 표현 금지
  "domain": "language",             // health | sport | language | hobby | study | custom
  "safety_profile": "neutral",      // medical | physical | neutral (§3-2)
  "weeks_total": 26,                // 4~52
  "phases": [                       // 합이 weeks_total 과 같아야 함
    {"id": "settle",  "name": "정착기", "from": 1,  "to": 3,  "desc": "매일 같은 자리에서 10분"},
    {"id": "build",   "name": "쌓기",   "from": 4,  "to": 14, "desc": "글자에서 문장으로"},
    {"id": "use",     "name": "써먹기", "from": 15, "to": 22, "desc": "듣고 말하고 틀려보기"},
    {"id": "keep",    "name": "유지",   "from": 23, "to": 26, "desc": "내 학습 루틴 확정"}
  ],
  "tracks": [ ... ],                // §4-2 (1개 이상)
  "intake": { "<track_id>": [ ... ] },   // §4-3
  "weeks": [ ... ],                 // §4-4, 길이 = weeks_total
  "support_pool": { "<track_id>": [ ... ] },   // §4-5
  "banners": { "<track_id>": {"경고": "...", "주의": "..."} },   // physical/medical 필수
  "transition": {"advance": 0.7, "simplify": 0.4},   // 기본값, 생략 가능
  "sources": [ {"key": "jlpt", "label": "JLPT 공식 출제 기준(N5)", "url": "..."} ]
}
```

### 4-2. 트랙

```jsonc
{"id": "reading", "name": "읽기 루틴", "icon": "book",     // icon 은 archetypes.js ICON 키(이모지 금지)
 "desc": "히라가나·짧은 문장을 하루 10분 소리 내 읽어요",    // 40자 이내
 "target_noun": "읽은 분량",                                // 행동 문구의 {tgt} 바인딩
 "recommend_when": []}                                       // medical 팩만: focus 신호 키 목록
```

트랙은 "같은 팩 안에서 고르는 변주"다. 골프 팩이라면 `range`(연습장 중심)·`home`(집에서 퍼팅·스윙 연습) 같은 식이다. 1개만 있어도 된다(그때는 트랙 선택 화면을 건너뛴다).

### 4-3. 문진

```jsonc
{"id": "level", "q": "지금 일본어는 어느 정도인가요?",        // 24자 이내
 "options": [{"label": "처음이에요", "value": "zero"}, {"label": "히라가나는 읽어요", "value": "kana"}],
 "why": "시작 주차의 분량을 여기에 맞춰요"}                    // 20자 이내 캡션
```

`label`(표시)과 `value`(매칭)를 분리한다. 27 §1-3 "코드 동기화" 항목이 지적한 문자열 리터럴 매칭 문제를 구조적으로 없앤다. 자유 텍스트·숫자 입력 문항은 허용하지 않는다.

### 4-4. 주차

```jsonc
{"w": 5, "theme": "문장 하나 통째로",                          // 20자 이내
 "goal_days": 5,                                              // 1~7
 "support_cap": 1,                                            // 0~2, 밴드 캡과 min
 "mission": "7일 중 5일, 예문 1개를 소리 내 읽고 기록",          // 40자 이내
 "unlock": "예문 카드팩",                                      // 선택, 보상 표현 금지("배지" 는 medical 프로필에서 게임요소 캡 대상)
 "actions": {
   "reading": {"id": "w5:read_sentence", "text": "예문 하나를 소리 내 읽고 어땠는지 하나만 탭",   // 30자 이내
               "cite": "jlpt", "minutes": 10,
               "input": {"kind": "choice", "options": ["술술", "더듬더듬", "못 읽음"]}}
 },
 "ask_chips": ["같은 문장을 며칠이나 반복하나요?", "발음은 어떻게 확인하나요?", "못 읽는 날은 어떻게 하나요?"],   // 3개, 각 24자 이내
 "warning_variant": { ... }                                   // medical/physical 만: 경고 밴드용 치환 행동(27 §2-5 관례)
}
```

`actions` 의 키는 트랙 id 전부를 덮어야 한다. `input.kind` 는 `tap | choice | scale` 셋만 허용한다(D5). 숫자·자유텍스트는 어떤 프로필에서도 받지 않는다(25 §E-1 "값은 라벨만" 원칙을 전 팩에 적용).

### 4-5. 보조 행동 풀과 선택 규칙

```jsonc
"support_pool": {
  "reading": [
    {"key": "shadow_1min", "text": "음성 따라 1분 섀도잉", "cite": "jlpt", "tags": ["listen"]},
    {"key": "kana_5",      "text": "헷갈리는 가나 5개만 다시 쓰기", "cite": "jlpt", "tags": ["kana"]}
  ]
},
"support_rules": {
  "reading": [
    {"when": {"level": "zero"}, "pick": ["kana_5", "shadow_1min"]},
    {"when": {"level": "kana"}, "pick": ["shadow_1min"]},
    {"default": ["shadow_1min"]}
  ]
}
```

`coaching_engine._select_keys()` 의 if/elif 를 데이터 규칙으로 옮긴 것이다. 규칙은 위에서부터 첫 매치, `pick` 순서 유지, 밴드 캡으로 자른다. 건강 팩은 `rag_db.coaching_plan` 저장을 그대로 유지하고(C15 deprecated-but-alive), 비건강 팩은 저장 없이 팩에서 매번 계산한다.

### 4-6. lint 규칙 (G4, CI 실패 조건)

| # | 검사 | 근거 |
|---|---|---|
| L1 | JSON Schema 통과, `weeks.length == weeks_total`, phases 가 1..weeks_total 을 빈틈·중복 없이 덮음 | 구조 |
| L2 | 모든 id·key 유일, `actions` 가 모든 트랙을 덮음, `support_rules.pick` 의 key 가 `support_pool` 에 존재 | 참조 무결성 |
| L3 | 글자수: 행동 30 · 캡션/why 20 · 버튼 12 · 칩 24 · 테마 20 · 미션 40 · 이름 20 · 태그라인 30 | 27 §0-4 |
| L4 | WC-C1·C2 스캔 0건(전 텍스트), 프로필별 추가 금칙 0건 | 컴플라 |
| L5 | 무비난 금칙: "실패"·"미달"·"놓친"·"결석"·"또 못" 등 27 §0-1 금지 어휘 0건 | 무비난 |
| L6 | `cite` 가 `sources` 에 존재, medical 프로필은 출처 화이트리스트(질병청·식약처·공단·WHO·보건소) 안 | 출처 |
| L7 | `input.kind ∈ {tap, choice, scale}`, choice 옵션 2~5개·각 12자 이내, `scale` 은 라벨 배열 3~5개 | 입력 |
| L8 | `goal_days` 1~7, 1주차 goal_days ≤ 3 권고(경고만), `support_cap` 0~2, 1~2주차 support_cap 0(정착기 원칙, medical/physical 필수) | 커리큘럼 원칙 |
| L9 | medical/physical: `banners.<track>.경고`·`.주의` 존재, `warning_variant` 가 행동 추가형 주차에 존재 | 밴드 캡 |
| L10 | 이모지 0개(아이콘은 ICON 키만) | design.md |
| L11 | 각 주차 `ask_chips` 정확히 3개 | 25 §B-6 |

---

## 5. 시스템 변경 요건 (FR)

### 5-1. 서버

| # | 요건 | 수용 기준 |
|---|---|---|
| FR-S1 | `routine_packs.py` — 로더·레지스트리·검증 | `get(pack_id, version=None)`, `catalog()`, 기동 시 전 팩 검증, 위반 시 `RuntimeError` |
| FR-S2 | `routine_engine` 팩 인자화 | 모든 공개 함수가 `pack` 을 첫 인자로 받거나 `Pack` 메서드가 됨. `health_12w` 팩으로 기존 22개 테스트 그대로 통과 |
| FR-S3 | 골든 테스트 | 현 코드의 `ROUTINE_ACTIONS`·`WEEKS`·`ASK_CHIPS`·`_BANNER`·`INTAKE_QUESTIONS`·`KB` 를 JSON 스냅샷으로 뽑아 두고, `health_12w` 팩에서 만든 값과 딕셔너리 동등 비교. 밴드 3종×주차 12×트랙 3 = 108 케이스의 `today_action`·`band_cap`·`support_items` 동등 |
| FR-S4 | `routine_program` 확장 | 컬럼 `pack_id TEXT DEFAULT 'health_12w'`, `pack_version INTEGER DEFAULT 1`, `phases_json TEXT`. 기존 행은 기본값으로 건강 팩에 귀속(무마이그레이션 회귀 없음). mig 025 + in-code ensure |
| FR-S5 | `routine_repo` 12 리터럴 제거 | `week_of`·`build_week_state`·`current_week` 이 `weeks_total` 인자/컬럼 사용 |
| FR-S6 | `GET /routine/packs` | 카탈로그 배열. 각 항목: id·name·tagline·domain·safety_profile·weeks_total·phases·tracks(카드용)·recommended(bool, medical 팩만 focus 매칭)·available(bool: 밴드 게이트 결과, 경고 밴드에서 physical 팩은 `available=false, reason="clearance_required"`) |
| FR-S7 | `POST /routine/start` | `pack_id` 필드 추가(기본 `health_12w`). 미지원 팩 400 `unknown_pack`, 트랙 검증은 팩 기준. `program_exists`·`track_change_cooldown` 정책은 유지(D2) |
| FR-S8 | `GET /routine/today` 페이로드 | `program.weeks_total`·`program.phase`(팩 phases 기준)·신규 `pack {id, name, weeks_total, phases[], safety_profile}` 블록. 기존 키·값은 건강 팩에서 골든 동일 |
| FR-S9 | `GET /routine/week-report` | 주차 clamp·`next` 계산이 `weeks_total` 기준. `trend_label`·`delta` 로직 불변 |
| FR-S10 | 컴플라 프로필 | `coaching_compliance.check_plan(text, band, profile="medical")` 로 확장. 프로필별 추가 정규식 세트. 기존 시그니처 호환(기본값 medical) |
| FR-S11 | 이벤트 | `routine_started`·`routine_checkin`·`routine_report_read` 에 `pack_id` 라벨(allowlist 값은 팩 id 정규식) |
| FR-S12 | `/diagnosis.recommended` | `pack_id: "health_12w"` 를 함께 반환. 비의료 팩 추천 로직은 없음(사용자 선택) |

### 5-2. 프론트

| # | 요건 | 수용 기준 |
|---|---|---|
| FR-F1 | 온보딩 트랙 선택 → **루틴 고르기** | `GET /routine/packs` 카탈로그 카드(이름·태그라인·기간·트랙 수). 건강 팩은 기존 추천 배지 유지. 팩 선택 → 트랙 선택(트랙 1개면 건너뜀) → 문진 → 미리보기 → 알림 |
| FR-F2 | "12주" 리터럴 18곳 제거 | `program.weeks_total`·`pack.phases` 로 렌더. `Timeline.PHASE()` 삭제, 페이로드 `phases[]` 로 라벨 |
| FR-F3 | 트랙 카드 리터럴 제거 | `onboard.js:146~148`·`health.js:71` 을 팩 `tracks` 로 |
| FR-F4 | 미리보기(T3) | 단계 수가 4개가 아니어도 렌더. 단계 설명은 `phases[].desc` |
| FR-F5 | 프로그램 탭 | 26주 타임라인이 스크롤 안에서 깨지지 않음. 히트맵 셀 수 = weeks_total×7 |
| FR-F6 | 재미 레이어 | 변경 없음. 팩과 무관하게 물·걸음·마음 3타일 유지(§8 E2) |

### 5-3. 작성 도구

| # | 요건 | 수용 기준 |
|---|---|---|
| FR-T1 | `scripts/pack_lint.py [pack_id|--all]` | §4-6 L1~L11 검사, 위반을 `파일:경로:규칙:메시지` 로 출력, exit 1. CI job 추가 |
| FR-T2 | `scripts/pack_new.py --id golf_6m --weeks 26 --tracks range,home --profile physical` | 스키마 유효한 빈 팩 생성(TODO 문구가 lint 에 걸리도록 30자 초과 플레이스홀더) |
| FR-T3 | 팩별 자동 테스트 | `tests/test_packs.py` 가 레지스트리의 전 팩을 파라미터화해 lint + 엔진 스모크(전 주차×트랙×밴드에서 `today_action`·`support_items` 예외 0) |
| FR-T4 | 작성 가이드 | `routines/README.md` — 커리큘럼 설계 원칙(§6), 필드 설명, lint 돌리는 법, PR 체크리스트 |
| FR-T5 | (D8, 선택) `scripts/pack_draft.py` | 브리프(도메인·기간·트랙·대상)로 Claude API 에 초안을 만들게 하되 출력은 파일로만, 자동 커밋 없음, lint 통과 전까지 사용 불가 |

---

## 6. "타당한 루틴"의 설계 원칙 (모든 팩의 커리큘럼 규칙)

25·27 에서 건강 커리큘럼에 적용한 원칙 중 도메인과 무관한 것만 추려 플랫폼 규칙으로 올린다. lint 가 기계적으로 잡는 것(L8)과 리뷰어가 보는 것을 나눈다.

| # | 원칙 | 기계 검사 | 리뷰 항목 |
|---|---|---|---|
| P1 | 오늘 할 것은 **1개**, 기록형(값·태그가 남는 행동) | actions 는 트랙당 1개, input 필수 | 행동이 "읽고 실천"이 아니라 "하고 남기기"인가 |
| P2 | 정착기(첫 2~3주)는 항목 추가·난이도 상향 없음 | 1~2주 support_cap=0 | 첫 주 goal_days 가 3 이하인가(첫 성공 경험) |
| P3 | 단계는 정착 → 확장 → 내재화 → 유지/전환의 흐름 | phases 4개 이상 권고(경고) | 마지막 단계가 "적게 남기기"(유지 루틴 확정)로 끝나는가 |
| P4 | 앵커링: 이미 매일 하는 일 뒤에 붙인다 | 문진에 앵커 시각 문항 존재(경고) | 행동 문구가 "언제"를 포함하는가 |
| P5 | 무너진 날의 복구 절차가 커리큘럼 안에 있다 | 내재화기 주차 중 `pass_or_log` 류 `tap` 행동 존재(경고) | "두 번 연속 거르지 않기" 같은 복구 미션이 있는가 |
| P6 | 출처가 있다 | L6 | 출처가 그 도메인의 공식 자료인가(개인 블로그 금지) |
| P7 | 성과를 약속하지 않는다 | L4 | "6개월이면 싱글", "N3 합격" 류 0건 |
| P8 | 매주 질문칩 3개로 상담 재진입 | L11 | 질문이 그 주 행동과 이어지는가 |

---

## 7. 샘플 팩 스케치 (스키마 검증용 — 전체 26주는 Phase 3 에서 작성)

### 7-1. `golf_6m` — physical, 26주, 트랙 `range`(연습장)·`home`(집)

| 주차 | 단계 | 테마 | 오늘의 행동(range) | 입력 | goal |
|---|---|---|---|---|---|
| 1 | 정착기(1~3) | 그립 잡고 10번 | 집이든 연습장이든 그립 잡고 빈 스윙 10번 후 기록 | tap | 3 |
| 2 | 정착기 | 같은 시각·같은 자리 | 어제와 같은 시각에 빈 스윙 10번, 느낌 하나 탭 | choice: 편함/뻣뻣/모름 | 5 |
| 4 | 쌓기(4~12) | 7번 아이언 하나로 | 7번 아이언 20구, 잘 맞은 공 비율 하나 탭 | choice: 절반 이상/몇 개/거의 없음 | 5 |
| 9 | 쌓기 | 무너지는 날 찾기 | 연습 뒤 오늘 상황 태그 하나 | choice: 평소대로/피곤/시간 부족/통증 | 5 |
| 10 | 쌓기 | 통증이면 쉬기 | 통증 태그가 있으면 오늘은 스트레칭만 하고 [해당없음] | tap + na | 5 |
| 14 | 써먹기(13~22) | 9홀 나가보기 | 이번 주 라운드·스크린 1회 예약하고 기록 | tap | 4 |
| 20 | 써먹기 | 못 한 날 복구 | 못 간 날은 [오늘은 패스] 한 번 | tap | 5 |
| 26 | 유지(23~26) | 내 연습 루틴 확정 | 6개월 중 가장 잘 지킨 연습 1개에 유지 표시 | tap | 4 |

안전: `safety_profile=physical` → 경고 밴드는 clearance 배너 고정·보조 캡 0·advance 금지. 도메인 금칙: "무릎/허리 아플 땐 ~하세요" 류 처방 0건, 통증은 항상 "쉬기·해당없음"으로만 처리. 출처: 대한골프협회 기초 교습 가이드, 국민체육진흥공단 생활체육 안내.

### 7-2. `japanese_6m` — neutral, 26주, 트랙 `reading`(읽기)·`listening`(듣기)

| 주차 | 단계 | 테마 | 오늘의 행동(reading) | 입력 | goal |
|---|---|---|---|---|---|
| 1 | 정착기(1~3) | 히라가나 5개 | 출근길·자기 전 히라가나 5개 소리 내 읽고 기록 | tap | 3 |
| 3 | 정착기 | 내 기준선 | 오늘 읽은 양이 평소보다 어땠는지 하나 탭 | choice: 비슷/많이/적게 | 5 |
| 5 | 쌓기(4~14) | 문장 하나 통째로 | 예문 하나 소리 내 읽고 어땠는지 하나 탭 | choice: 술술/더듬더듬/못 읽음 | 5 |
| 12 | 쌓기 | 무너지는 날 찾기 | 오늘 상황 태그 하나 | choice: 평소대로/야근/약속/피곤 | 5 |
| 16 | 써먹기(15~22) | 틀려보기 | 짧은 문장 하나 써 보고 확인했는지 탭 | tap | 5 |
| 19 | 써먹기 | 못 한 날 복구 | 못 한 날은 [오늘은 패스] | tap | 5 |
| 24 | 유지(23~26) | 내 패턴 한 줄 | 앱이 정리한 내 학습 패턴 확인/수정 | choice: 맞아요/조금 달라요 | 4 |
| 26 | 유지 | 유지 루틴 확정 | 가장 잘 지킨 습관 1개에 유지 표시 | tap | 4 |

안전: `neutral` → 밴드 캡 없음, 응급만 중단. 도메인 금칙: 급수 합격·기간 보장 표현 0건. 출처: JLPT 공식 출제 기준, 국제교류기금 「まるごと」 교재 목차.

두 팩 모두 §6 P1~P8 을 만족하도록 설계했다. 26주 전문은 Phase 3 에서 lint 를 통과시키며 채운다.

---

## 8. 결정 요청 (D1~D9) — 승인 시 아래 권고안대로 진행

| # | 결정 | 선택지 | **권고** | 이유 |
|---|---|---|---|---|
| D1 | 팩 저장 위치 | (a) 레포 JSON 파일 + PR 리뷰 (b) DB 테이블 + 관리자 API | **(a)** | git diff·CI lint·롤백이 공짜. 진행 중 프로그램의 버전 고정은 `pack_version` 컬럼 + 파일 안 `history[]` 로 해결. (b)는 CMS 가 필요해질 때 |
| D2 | 동시 진행 프로그램 수 | (a) 1개 유지, 팩 교체는 `change_track` 관례 (b) 최대 2개(건강 1 + 비건강 1) | **(a) v1, (b) 는 Phase 4 검토** | 홈 1콜·스트릭·주간 리포트·재미 레이어가 전부 "프로그램 1개" 전제. (b)는 홈 히어로가 2개가 되어 "오늘 할 것 1개" 원칙과 충돌하므로 별도 UX 결정이 필요 |
| D3 | 안전 프로필 3종과 비의료 팩의 밴드 완화 | §3-2 표 | **표대로** | 응급은 어떤 팩도 못 끈다. physical 은 운동 트랙과 같은 규칙, neutral 은 배너·캡 없음 |
| D4 | 기간 자유도 | 4~52주, 단계 자유 | **채택** | 26주(6개월)가 첫 요구. 52주 상한은 히트맵·타임라인 렌더 한계 |
| D5 | 입력 위젯 | (a) tap/choice 만 (b) + scale(라벨형 3~5단) (c) + 숫자 | **(b)** | 골프 "잘 맞은 비율", 어학 "술술/더듬" 같은 정도 표현이 필요. 숫자는 "값은 라벨만" 원칙과 충돌 |
| D6 | 출처 필수 범위 | (a) 전 프로필 필수 (b) medical 만 | **(a)** | 타당성의 최소 증거. 비의료는 화이트리스트 없이 `sources` 존재만 검사 |
| D7 | 카피 예산·무비난 금칙 적용 범위 | (a) 전 팩 동일 (b) 건강만 | **(a)** | 화면 레이아웃 제약(30자)과 제품 톤은 도메인과 무관 |
| D8 | LLM 초안 생성 도구 | (a) 포함(초안 전용, lint·리뷰 게이트) (b) 제외 | **(a), Phase 2 후반** | 26주×트랙 2×행동·칩·미션을 손으로 쓰면 팩 하나에 수백 문장. 초안은 도구가, 검수는 사람이 |
| D9 | 첫 샘플 팩 | golf_6m + japanese_6m | **채택** | 요청 예시 그대로. physical·neutral 프로필을 하나씩 검증 |

---

## 9. 작업 계획 (Phase 0~4)

| Phase | 내용 | 산출물 | 완료 기준 |
|---|---|---|---|
| **0 추출** | 현 커리큘럼을 JSON 으로 뽑고 골든 스냅샷 고정 | `routines/_schema/pack.schema.json`, `routines/packs/health_12w/pack.json`, `tests/golden/health_12w.json`, `routine_packs.py`(로더만) | 스냅샷 == 팩 로드 결과. 기존 코드는 아직 안 건드림 |
| **1 엔진·저장소·API** | 엔진 팩 인자화, repo 12 제거, mig 025, `/routine/packs`, `start.pack_id`, 페이로드 `pack` 블록, 컴플라 프로필 | FR-S1~S12 | 기존 22+11 테스트 통과 + 골든 108 케이스 동등 + 신규 라우트 테스트 |
| **2 프론트·도구** | 루틴 고르기 화면, 12 리터럴 제거, lint·스캐폴드·팩 자동 테스트·CI·작성 가이드, (D8) 초안 도구 | FR-F1~F5, FR-T1~T5 | `pack_new` 로 만든 빈 팩이 lint 에서 떨어지고, 채우면 온보딩에 뜬다 |
| **3 샘플 팩** | golf_6m·japanese_6m 26주 전문 작성, lint 통과, 로컬 E2E | 팩 2개 + `routines/README.md` 갱신 | 코드 0줄 변경으로 두 팩이 홈·프로그램·리포트에서 동작 |
| **4 하드닝·배포** | 접근성(26주 타임라인), 스테이징 배포, 27 정본에 "팩 1호" 관계 명시, D2(b) 재검토 | 배포 기록, PR | 온라인 E2E 3팩 |

의존: 0 → 1 → (2 ∥ 3 의 골프 팩 초안) → 3 → 4. Phase 3 의 팩 작성은 Phase 2 의 lint 가 있어야 검증되므로 lint 를 Phase 2 앞쪽에 둔다.

---

## 10. 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| 27 정본 카피가 코드 상수와 이미 어긋남(27 §0-4 "38~46자 초과" 지적) | 골든 스냅샷을 "현 코드"로 잡으면 초과 카피가 팩 1호에 그대로 들어가 lint L3 에 걸림 | Phase 0 에서 팩 1호는 **현 코드 그대로** 추출(무회귀 우선), lint L3 는 `health_12w` 에 한해 경고로 시작 → 27 §2 교체본 반영을 별도 PR(카피 교체)로 분리 |
| `rag_db.coaching_plan` 결합 | 비건강 팩은 저장 위치가 없음 | 팩 보조 풀은 런타임 계산, 저장은 건강 팩만(C15 유지) |
| 프론트 리터럴 누락 | 26주 팩에서 "12주" 문구가 남음 | FR-F2 를 grep 기반 테스트로 고정(`web/js` 에 `12주` 리터럴 0건) |
| 팩 버전 변경 중 진행 프로그램 | 주차 수가 바뀌면 진도 계산 붕괴 | `weeks_total` 변경은 `version` 증가 필수 + 프로그램은 시작 시 버전 고정(L1 에 "history 에 이전 버전 보존" 검사) |
| 비의료 팩 사용자의 응급 밴드 | 어학 루틴 중 앱 전체 중단이 과해 보일 수 있음 | 의도된 동작. 안전 게이트 공유 원칙(18 §0)을 README 에 명시 |
| LLM 초안의 금칙 위반 | 성과 보장·처방 표현 유입 | lint 게이트 + 초안 파일은 `drafts/` 에만 생성, 팩 디렉터리로 옮기는 건 사람 |

---

## 11. 승인 후 첫 행동

1. D1~D9 확정값을 이 문서 §8 에 기록(권고안 그대로면 "승인 2026-09-xx" 한 줄).
2. Phase 0: 스키마 파일·추출 스크립트·골든 스냅샷·`health_12w/pack.json` 커밋.
3. Phase 1 착수 전, 골든 108 케이스가 초록인 상태를 CI 에 올린다.

---

## 12. 구현 기록 (2026-09-29)

### 12-1. 계획과 달라진 점

| 항목 | 계획 | 구현 | 이유 |
|---|---|---|---|
| 팩 파일 이름 | `routines/packs/<id>/pack.json` + `history[]` | `routines/packs/<id>/v<version>.json`, 버전마다 파일 하나 | 진행 중 프로그램의 버전 고정이 파일 존재만으로 보장된다. 로더가 "디렉터리 = id, 파일 = v<version>" 을 검사 |
| 보조 행동 규칙(§4-5) | 위에서부터 첫 매치, `pick` | **누적** 규칙: `when`(AND, `null`=미응답) · `unless`(하나라도 걸리면 제외) → `add`, 결과가 비면 `default` | 기존 `_select_keys()` 의 if 누적 로직을 그대로 옮겨야 골든이 같아진다 |
| 풀 크기 상한 | 없음 | `support_pool_cap` (`{"default": 4, "경고": 2}`) | 기존 코드의 경고 밴드 풀 2개 규칙 |
| 경고 치환 행동 | `warning_variant` | `weeks[].warning_actions.<track>` | 트랙별 치환이 필요 |
| `routine_program.phases_json` (FR-S4) | 추가 | **추가 안 함** — `pack_id`·`pack_version` 만 | 단계는 고정된 버전 파일에서 읽으면 된다(중복 저장 불필요) |
| 추출 스크립트 | 커밋 | 1회 사용 후 삭제. 골든 생성기 `scripts/routine_golden.py` 만 유지 | 팩 JSON 이 정본 |
| 팩 테스트 파일 | `tests/test_packs.py` | `tests/test_routine_packs.py`(레지스트리·lint·스모크·골든) + `tests/test_routine_packs_runtime.py`(라우트) | 기존 이름 규칙 |
| lint 추가 | — | L0(TODO 자리표시자), P4 앵커·P5 복구는 경고, physical 경고 치환 행동 누락은 error | 스캐폴드가 lint 에서 떨어지게(FR-T2), physical 안전 |
| 경고 밴드 physical 신규 시작 | 카탈로그 `available=false` | + `POST /routine/start` 409 `clearance_required` | 우회 방지 |
| 프론트 | FR-F1~F5 | 팩 1개면 고르기 화면, 트랙 1개면 트랙 화면을 건너뜀(기존 건강 온보딩과 동일 경험). `/routine/today` `weeks[]` 에 `theme` 추가 | 26주 타임라인 가독성 |

### 12-2. 진행

| Phase | 커밋 | 결과 |
|---|---|---|
| 0 추출 | `e30216b` | `health_12w/v1.json`, 골든 스냅샷, 로더 |
| 1 엔진·저장소·API | `766aa19` | 팩 인자화, mig 025(`pack_id`·`pack_version`), `/routine/packs`, 컴플라 프로필. 81개 라우트 페이로드 전후 비교 값 변화 0(키 추가만) |
| 2a 도구 | `c1ac881` | `pack_lint.py`(CI 게이트)·`pack_new.py`·JSON Schema·작성 가이드 `routines/README.md` |
| 2b 프론트 | `b079529` | 루틴 고르기, "12주" 리터럴 0건(테스트로 고정) |
| 3 샘플 팩 | `bc987bb` | `golf_6m`·`japanese_6m` 26주, lint 0 error·0 warning, 코드 변경 0줄 |
| 4 | `18a02b7` | 스테이징 배포(BFF rev 00018→00019, 이미지만 교체·env 보존) + GCS 정적 사본. 온라인 스모크 통과 |
| D8 초안 도구 | `3eda845` | `scripts/pack_draft.py` — 브리프 → 스캐폴드 구조 + LLM 문구 → lint·초안 점검 → 걸린 주차만 재작성 → `routines/drafts/`. 샘플 브리프 `running_8w` 실측: 호출 4회·3분, error 0 · warning 1 |
| 5 건강 카피 교체 | (이 커밋) | `health_12w/v2.json` — 27 §2 행동 36개·미션·§4 질문칩·§5 출처(`hpa`·`phc_quit` 추가, `kspo` 제거)·§2-5 경고 치환(5·6·8·9주)·§3-6 배너(이모지 없음, "진단은 아니에요")·§1-3 문진(라벨만 교체, value 유지, '목표 기간'·'체중' → 기록 앵커 문항). 행동 id·분·입력 형태 불변. lint 0 error·0 warning. v1 은 그대로(진행 중 프로그램 고정), 골든·레거시 `/coaching/*` 은 v1 고정 |

전체 테스트 1069 passed / 12 skipped. 로컬 E2E(모바일 375): 경고 밴드 페르소나 → 골프 비활성 → 일본어 시작 → 홈 → 완료 → 프로그램 26주 → 주간 리포트.

### 12-3. 남은 일

- 샘플 팩 내용은 **도메인 전문가 검수 전**이다(골프 코치·일본어 강사). 출처 URL 중 `kgagolf.or.kr` 은 사내망 차단으로 열어 보지 못했다.
- ~~`health_12w` L3·L10 경고~~ → v2 로 해소. `LEGACY_WARN_ONLY` 는 `(id, version)` 키로 바꿔 v1 에만 남김(옛 버전 파일은 고치지 않는다).
- 27 카피 중 팩 스키마에 자리가 없어 v2 에 못 넣은 것: 메타 캡션(§2 `META_CAPTION`)·완료 직후 코치 한 줄(`COACH_LINE`)·경고 밴드 주간 미션(§2-5)·자동 하향 셀(§2-6). 넣으려면 `Action.meta`·`Action.coach`·`Week.warning_mission` 필드 추가(스키마 변경 PR).
- v2 문진의 `anchor` 답은 `intake_json` 에만 저장된다. `routine_program.anchor`·알림 기본 시각으로 흘리는 연결(27 §1-3)은 코드 작업으로 남음.
- L9 규칙 변경: medical 팩은 원행동이 기록형이라 행동을 얹는 주차만 치환한다(27 §2-5) → 치환이 팩에 하나도 없을 때만 경고. physical 은 주차별 필수 그대로.
- D8 초안 도구는 완료. 교훈: lint 0 error 여도 초안 버릇(질문칩이 앱→사용자 방향, 경고 배너에 질환 나열, 전부 tap)이 있어 초안 전용 점검을 따로 둠. 모델은 llm_router 기본(OpenAI) — 계획의 Claude API 는 이 저장소에 SDK·키가 없어 주입식(`LLM` 콜러블)으로 열어 둠.
- ~~`health_12w` 5주차 보기의 '해당없음'~~ → v2 에서 뺌.
- D2(b) 건강 1 + 비건강 1 동시 진행 — 홈 UX 결정 필요.

