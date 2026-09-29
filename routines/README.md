# 루틴 팩 작성 가이드

루틴 하나(예: 골프 6개월, 일본어 6개월)는 **JSON 파일 하나**다. 코드는 건드리지 않는다.
설계 정본: [`docs/plan/28-routine-pack-platform.md`](../docs/plan/28-routine-pack-platform.md).

```
routines/
  packs/<pack_id>/v<version>.json   ← 팩 본문(버전마다 파일 하나, 이전 버전은 지우지 않는다)
  _schema/pack.schema.json          ← 에디터 자동완성용 JSON Schema(자동 생성)
```

## 1. 5분 시작

```bash
python scripts/pack_new.py --id golf_6m --weeks 26 --tracks range,home --profile physical --domain sport --name "골프 6개월 루틴"
# routines/packs/golf_6m/v1.json 이 생긴다. 구조는 유효하고 문구 자리는 전부 TODO.
python scripts/pack_lint.py golf_6m          # TODO 가 남아 있으면 L0 error
python scripts/pack_lint.py golf_6m --warn   # 권고(경고)까지 보기
python -m pytest tests/test_routine_packs.py # 전 팩 lint + 엔진 스모크(전 주차 × 트랙 × 밴드)
```

lint 가 0 error 가 되면 서버를 재시작하는 것만으로 온보딩 "루틴 고르기" 에 뜬다(`GET /routine/packs`).

## 2. 안전 프로필 — 먼저 고른다

| 프로필 | 쓰는 곳 | 경고 밴드(건강 페르소나) | 추가 금칙 |
|---|---|---|---|
| `medical` | 건강 관리(식단·운동·생활습관) | 보조 행동 0, 주차 진급 금지, 진료 우선 배너 | 효능 표방·처방성 |
| `physical` | 몸을 쓰는 취미(골프·러닝 등) | 새로 시작 불가(409 `clearance_required`), 진행 중이면 보조 0·진급 금지·`warning_actions` 로 치환 | + 성과 보장, 부상·통증 처방 |
| `neutral` | 어학·공부·악기 등 | 제한 없음 | + 성과 보장 |

**응급 밴드는 어떤 팩이든 루틴 전체를 멈춘다.** 팩이 끌 수 없다(안전 게이트 공유, 18 §0).
배너 문구는 팩이 쓰지만 노출 여부·캡·진급 규칙은 프로필이 정한다.

## 3. 필드 요약

| 필드 | 규칙 |
|---|---|
| `id` | `[a-z][a-z0-9_]{1,39}`, 디렉터리 이름과 같아야 한다 |
| `version` | 파일 이름 `v<version>.json` 과 같아야 한다. 진행 중 프로그램은 시작 버전에 고정되므로 **주차 수·행동이 바뀌면 새 버전 파일을 만든다** |
| `weeks_total` | 4~52. `weeks` 길이와 같다 |
| `phases` | 1..weeks_total 을 빈틈·겹침 없이 덮는다. 4단계 권고(정착 → 쌓기 → 써먹기 → 유지) |
| `tracks[]` | 같은 팩 안의 변주(골프: 연습장/집). `icon` 은 아래 아이콘 키만 |
| `intake.<track>[]` | 문진. `options` 는 `{label, value}` — 매칭은 `value` 로 한다. 자유 입력 없음 |
| `weeks[].actions.<track>` | 오늘 할 것 **1개**. 모든 트랙을 덮는다. `cite` 는 `sources[].key` |
| `weeks[].actions.*.input` | `tap`(옵션 없음) · `choice`(2~5개) · `scale`(라벨 3~5개). 숫자·텍스트 입력 없음 |
| `weeks[].warning_actions` | 경고 밴드용 치환 행동. `physical` 은 전 주차·전 트랙 필수 |
| `weeks[].support_cap` | 0~2. 밴드 캡과 작은 쪽을 쓴다. 정착기는 0(medical·physical 필수) |
| `weeks[].ask_chips` | 정확히 3개. 그 주 행동에서 이어지는 질문 |
| `support_pool` / `support_rules` | 보조 행동 풀과 문진 기반 선택 규칙. 규칙은 **누적**: `when`(모두 맞으면, `null`=미응답) 이면서 `unless` 에 하나도 안 걸리면 `add` 를 더한다. 아무것도 안 붙으면 `default` |
| `support_pool_cap` | 밴드별 풀 최대 크기(`{"default": 4, "경고": 2}`) |
| `banners.<track>.<band>` | medical·physical 은 `주의`·`경고` 필수 |
| `sources[]` | 출처. medical 은 공신력 보건 기관만. 다른 프로필도 공식 교습 지침·시험 요강·교재 수준 |

아이콘 키: `star flame cup cloud bowl run moon book headphones golf home pen leaf music`
(추가하려면 `routine_packs.ICONS` 와 `web/js/archetypes.js` ICON 에 같이 넣는다 — 테스트가 동기를 확인한다.)

## 4. 타당한 루틴의 원칙 (P1~P8)

| # | 원칙 | 기계 검사 | 리뷰어가 볼 것 |
|---|---|---|---|
| P1 | 오늘 할 것은 1개, 하고 **남기는** 행동 | 트랙당 행동 1개, input 필수 | "읽고 실천" 이 아니라 "하고 탭" 인가 |
| P2 | 정착기엔 더하지 않는다 | 정착기 `support_cap` 0 (L8) | 1주차 `goal_days` ≤ 3 (첫 성공) |
| P3 | 정착 → 확장 → 내재화 → 유지 | 단계 4개 권고 | 마지막 단계가 "적게 남기기"(유지 루틴 확정)로 끝나는가 |
| P4 | 이미 하는 일 뒤에 붙인다 | 앵커(언제) 문항 권고 | 행동 문구에 "언제" 가 있는가 |
| P5 | 무너진 날의 복구가 커리큘럼 안에 | 내재화기 이후 `tap` 행동 권고 | "두 번 연속 거르지 않기" 같은 복구 주차가 있는가 |
| P6 | 출처가 있다 | L6 | 그 도메인의 공식 자료인가(개인 블로그 금지) |
| P7 | 성과를 약속하지 않는다 | L4 | "6개월이면 싱글", "N3 합격" 류 0건 |
| P8 | 매주 질문칩 3개로 상담 재진입 | L11 | 질문이 그 주 행동과 이어지는가 |

톤: 미실천을 규정하지 않는다(L5 금칙 — 실패·미달·놓친·결석·또 못·게으름·벌칙·포기). 이모지 금지(L10).

## 5. lint 규칙

| 규칙 | 내용 | 수준 |
|---|---|---|
| L0 | `TODO` 자리표시자 | error |
| L1·L2 | 구조·참조 무결성(주차 수, 단계 범위, 트랙 커버, cite, 규칙 참조, id 유일) — 로드 자체가 실패 | error |
| L3 | 글자수 예산(행동 30 · 칩 24 · 테마 20 · 미션 40 · 옵션 12 · 이름 20 · 태그라인 30 …, `routine_packs.BUDGET`) | error |
| L4 | 컴플라 스캔(효능 표방·처방성 + 프로필 추가 금칙) | error |
| L5 | 무비난 금칙어 | error |
| L6 | medical 출처 화이트리스트 / 안 쓰는 출처 | error / warn |
| L7 | 입력 위젯 옵션 수 | error |
| L8 | 정착기 보조 0 / 1주 목표·단계 수·앵커·복구 | error / warn |
| L9 | 밴드 배너 · 경고 치환 행동(physical) | error |
| L10 | 이모지 · 모르는 아이콘 키 | error |
| L11 | 질문칩 3개 | error |

`health_12w` 는 기존 코드에서 옮긴 팩이라 L3·L10 을 경고로만 낸다(`LEGACY_WARN_ONLY`). 새 팩엔 예외가 없다.

## 6. PR 체크리스트

- [ ] `python scripts/pack_lint.py <id>` 0 error, `--warn` 의 권고는 이유가 있어 남긴 것만
- [ ] `python -m pytest tests/test_routine_packs.py` 통과
- [ ] 기존 버전을 고쳤다면 새 `v<n+1>.json` 으로 만들었다(진행 중 사용자 보호)
- [ ] 출처 URL 을 직접 열어 확인했다
- [ ] 1주차·정착기 마지막 주·복구 주차·마지막 주 행동을 소리 내 읽어 봤다(무비난·30자)
- [ ] physical 이면 `warning_actions` 가 운동을 쉬게 하는 쪽인가(통증은 "쉬기·해당없음" 으로만)
- [ ] 스키마를 바꿨다면 `python scripts/pack_lint.py --schema` 로 `_schema/pack.schema.json` 갱신
