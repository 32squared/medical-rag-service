# 검진수치 밴드 시드 — 구조·라벨분리·deny-list (구현 스펙)

> 작성: 2026-06-20 · [10-data-utilization-matrix.md](10-data-utilization-matrix.md) §9 "검진수치 밴드 시드 11종 확장" 선결과제를 구현 스펙으로 전개.
> 4관점 2회차(데이터분석가=밴드 정의 / 아키텍트=M7 구조·lookup 계약 / 비평가=진단라벨 위험 / 기획자=종합·분류) 산출.
> 대상 코드: `seed_reference_ranges.py`, `migrations/010_vital_reference_ranges.sql`, `vital_input.py`, `rag_engine.py`(프롬프트팩·인용검증), `citation_verifier.py`. **본 문서는 설계만 — 코드 미수정.**

---

## 0. 한 줄 결론 (설계를 바꾸는 발견)

비평가가 코드로 확인: **기존 시드가 이미 `"고혈압 1기"`(`:54`)·`"당뇨병 기준"`(`:91`)·`"1단계 비만"`(`:231`) 같은 진단명 라벨을 담고 있다.** 이 라벨은 KB 인용 본문(`build_reference_documents` + `_DISCLAIMER`)으로는 안전하지만, **개인 검진수치에 매칭해 "당신 기록은 고혈압 1기"로 출력하면 디스클레이머 무관 무면허 진단**(의료법 §27, 07 §2-1). → 진짜 위험축은 09 §2의 "원시값 vs 라벨"이 아니라 **"일반 사실 vs 개인 귀속"**. 따라서 이번 스펙의 핵심은 ① **출력 라벨 사전을 시드 라벨과 물리 분리**, ② **진단 컷오프/맥락의존 수치(eGFR·골밀도·요단백·LDL)는 시드 확장이 아니라 deny-list**, ③ 깔끔한 수치만 기계가독 밴드로 시드화.

---

## 1. 불변식 교정 — "원시값 0" → "개인 귀속 진단 0"

| 기존(09 §8 I1) | 교정 |
|---|---|
| 원시 측정값이 출력·국외전송에 0건 | (유지) + **I2′: 개인에게 귀속된 진단 컷오프/질환명 라벨 0건** |

- **합법(일반 사실)**: "공복혈당 126 이상은 당뇨병 진단을 고려하는 기준입니다 [R#]" — 주어 없음, 인구집단. population test 통과.
- **위법(개인 귀속)**: "당신의 공복혈당은 당뇨병 기준에 해당합니다" — 특정인에 컷오프 귀속 = 진단.
- 경계는 **출처가 아니라 귀속(attribution)**. 라벨이라 안전한 게 아니라, *개인에 귀속된 진단 라벨이 가장 위험*.

**출력 라벨 사전 분리 (필수)**: 사용자 findings는 시드의 임상/질환 라벨을 **절대 재사용하지 않고** 아래 중립 사전에서만 생성.

| 시드 임상 라벨(KB 인용 전용·동결) | 사용자 출력 라벨 |
|---|---|
| 정상혈압 / 당뇨병 기준 / G3a / 골다공증 / 1단계 비만 … | **안정** = "현재 측정 기준 특이소견 없음(다른 위험요인 별개)" |
| 고혈압전단계 / 경계 / 골감소 … | **주의** = "관리 권장 구간 — 의료진 확인 권장" |
| 고혈압 1·2기 / 당뇨병 기준 / 매우 높음 … | **경고** = "기준 초과 — 의료진 확인 권장" |

질환·병기명("고혈압 1기", "당뇨병 기준", "N단계 비만", "CKD 3기", "골다공증", "이상지질혈증")의 **사용자 findings 출고 0 게이트**.

**I2 스캐너 보강(검증된 구멍)**: 현행 `citation_verifier.py:49`(`(당신은|환자분은)…입니다`)는 종결어미 정규식이라 **"~기준에 해당하는 수치가 확인됩니다" 명사구 진단을 통과**시킨다. → findings 주입 직전 **질환명 명사 사전 매칭 게이트** 추가(휴리스틱 종결어미가 아니라 명사 화이트리스트; 07 §9.1 false-negative 문제와 동형).

---

## 2. 시드 vs deny-list 분류 (데이터분석가 ↔ 비평가 종합)

데이터분석가가 13종 밴드를 정의했으나, 비평가가 진단컷오프·맥락의존 수치를 deny로 반려. 기획자 조정 결과:

### 2-A. 시드화 (깔끔·저논쟁 — 라벨 어휘만 중립화하면 즉시 가능)

| 신호키 | 밴드(안정/주의/경고 경계) | 분리축 | 공인 출처 |
|---|---|---|---|
| `total_cholesterol` | <200 / 200–239 / ≥240 | — | 한국지질·동맥경화학회 5판(2022)+ATP III |
| `triglycerides` | <150 / 150–199 / ≥200(≥500 경고) | **공복 필수** | 동상 |
| `hemoglobin` | 남≥13·여≥12 / 빈혈범위 / <8 | **성별**(임신 별도) | WHO 2024 |
| `hdl_cholesterol` | ≥40(안정) / <40(주의) **방향반전** | 성별(목표) | 한국지질학회 5판 |
| `waist_circumference` | 남<90·여<85 / ≥(주의) | **성별** | 대한비만학회 8판(2022) |
| `ast`,`alt`,`ggt` | 참조내 / 경도상승 / 현저상승 | **검사실 ULN 우선**·GGT 성별 | 대한진단검사의학회(검사실 ULN) |
| `creatinine` | 남0.7–1.3·여0.5–1.1 / 초과 | 성별·**eGFR 환산 우선** | 대한진단검사의학회 |

> 간수치·크레아티닌은 **검사실 인쇄 참조범위 동봉 시 그 값 우선**, 없으면 보수 라벨 + 캐비엇(Lv2 천장). 단위 검증 필수(§6).

### 2-B. deny-list (밴드 라벨 영구 금지 — 비평가 §5-2)

| 신호 | 금지 이유 | 허용 활용(라벨 외) |
|---|---|---|
| `egfr` | 급성/만성 미구분·연령 생리저하 — 단일값 진단 불가. "CKD N기"=진단 | 존재 ack + "신장내과 상의" + 일반기준 인용 |
| `bmd_tscore` | 부위·연령·성별·Z-score 분기. "골다공증"=진단 | 존재 ack + 골밀도 검사주기 안내 |
| `urine_protein_dipstick` | 일시적·기립성·발열 양성 흔함(거짓경보 1위) | "재검·정량(ACR) 확인" 안내만 |
| `ldl_cholesterol` | 목표 컷오프가 심혈관 위험계층별 가변. "이상지질혈증"=진단 | 일반기준 인용 + "종합 위험도는 의료진" |

**핵심 논증(비평가 §5)**: "라벨 못 붙임 = 방치(Lv0)"가 아니다. 활용에는 ① 존재·신선도 ack ② 수검주기 갭(O9) ③ 의료진 연결 트리거 ④ 일반기준 인용 — 라벨 없는 4축이 있다. deny-list 수치도 **고아 0 충족**. "활용 = 밴드 라벨"이라는 암묵 등식이 가장 위험한 수치를 밴드화 대상으로 끌어올린 근원.

### 2-C. 조건부 유지 (기존 시드 — 라벨 어휘 교체 필수)

`blood_pressure`("고혈압 1·2기"→"관리권장/기준초과 구간"), `bmi`("N단계 비만"→"기준 초과 구간"), `glucose`/`hba1c`("당뇨병 기준"→"기준 초과 — 의료진 확인 권장"). + 측정시점 결합(§6) + 단위 검증.

---

## 3. 기계가독 밴드 스키마 (M7 — 아키텍트)

자연어 `rule`은 **KB 본문용으로 유지**, lookup용 `bands` 구조를 **같은 `ranges` 원소에 병기**(공존).

### 3.1 Band 객체
```jsonc
{ "label":"고혈압전단계",          // KB 본문용(불변)
  "label_user":"주의",            // 사용자 3단 (§1 중립 사전)
  "axis":"systolic",             // 다축 신호 측정축(단축이면 생략)
  "min":130, "max":139, "min_inclusive":true, "max_inclusive":true,  // 단측=null 경계
  "applies_to":{"sex":null,"age_min":null,"age_max":null,"fasting":null,"context":null},
  "qualitative_value":null,       // 정성(요단백): "negative"|"1+"... — min/max 대신
  "stage":null,                   // 단계형(eGFR): "G3a" / 골밀도 "osteopenia"
  "note":"가정혈압 135/85 기준", "cite_doc_id":"ref.blood_pressure.kr" }
```
**4 표현형 손실 0**: ① 단측 부등호=`null 경계 + *_inclusive`(자연어 "이상/초과/미만" 파싱 영구 제거) ② 다축 "또는"=축별 밴드 분해 + lookup이 `label_user` 최댓값(보수)으로 합성 ③ 정성=`qualitative_value` ④ 단계·부위의존=`stage`+`applies_to`.

### 3.2 시드 진화 (기존 안 깨고)
- `_RANGES[*].ranges` 각 원소에 `rule`(불변) 옆 `bands` 추가. `build_reference_documents`는 `rule`만 읽으므로(`seed:321`) **KB 인용 본문 바이트 동일**(회귀 가드: 본문 골든 스냅샷 1건). `build_reference_rows`의 `json.dumps(ranges)`(`:287`)가 `bands`를 자동 직렬화 → `ranges_json`에 실림. **lookup은 `bands`키만 소비**.
- `migrations/012_vital_reference_bands.sql`(신규 — **011은 conversation_compat이 점유, 012가 빈 슬롯**): `schema_version INTEGER DEFAULT 1` 추가, `bands` 채운 행만 `2`. lookup은 `schema_version>=2`만 신뢰(미구조화 행 **fail-closed**). `ranges_json`은 TEXT JSON 유지(정규화 분해 안 함 — 010 단순성). 멱등 `ADD COLUMN IF NOT EXISTS`.
- **공존 불변식 CI**: 각 밴드 `(min,max,inclusive)`가 `rule` 자연어와 정합(rule "130-139" ⇒ band 130/139). 사람이 둘을 따로 고치다 어긋나는 사고 차단.

---

## 4. `vital_rules.lookup` 계약 (아키텍트)

```python
def lookup_band(signal_key, value, *, sex=None, age=None, fasting=None,
                context=None, locale="KR", device_grade="unverified") -> Band
```
반환 `Band`: `{signal_key, label_user, stage?, qualitative_value?, cite_doc_id, match, note}` — **원시 value·min·max 미반환**(밴드 식별자·인용만).

**결정적 절차(순서 고정, fail-closed)**: ① deny-list 게이트(§2-B·워치 ECG 등 → `match:"denied"`, 조회 안 함) → ② device_grade 미검증이면 임상밴드 비활성(I8) → ③ 행 SELECT(`signal_key·locale·is_active·schema_version>=2`, 인구 우선순위 tie-break 고정) → ④ `applies_to` 필터(sex/age/fasting/context 정확 일치) → ⑤ 경계 매칭(`*_inclusive` 단독 책임 / 정성=문자열 일치 / 다축=`label_user` 최댓값) → ⑥ `Band` 조립.

**비-`ok` 전부 finding 미생성**(라벨 0, 거짓안심 0): `no_match`(매칭0·환각 방어), `ambiguous`(밴드겹침→가장 보수 + 시드버그 신호), `out_of_range`(센서한계), `denied`. 침묵 평균·임의선택 금지(I11).

---

## 5. 인용 `[R#]` 배선 (아키텍트 — 결정적 검증 단일 전제)

`[R#]`는 독립 ID가 아니라 **`chunks` 검토자료 팩의 위치 `[N]` 슬롯**이다(`_build_user_prompt:1800` 1-based, `_validate_and_fix_citations:1972`가 `1..len(chunks)` 밖이면 마커 제거).

**단일 전제**: vital_rules가 finding 생성에 쓴 모든 `cite_doc_id`의 **참조범위 KB 문서를 같은 턴 `chunks`에 강제 동반 적재**. 누락 시 마커가 `>len(chunks)`로 제거돼 근거 증발 → **누락 시 finding 자체 드롭(fail-closed)**.
- `cite_doc_id` ↔ KB 문서 조인: `build_reference_documents`의 `document_id`가 UUID라 비결정적 → **`metadata.cite_doc_id="ref.blood_pressure.kr"` 불변 별칭을 메타에 추가**해 결정적 조인.
- 검증 통과: `check_citation_grounding`(`citation_verifier.py:90`)은 finding 내용어 ↔ ref 청크 본문 ≥20% 겹침 요구. ref 본문이 자연어 rule을 담으므로 finding에 "혈압/주의/구간" 내용어 두면 통과(shadow — 미달은 라벨만).

---

## 6. 추가 안전 게이트 (비평가 — 배선 선결조건)

| 게이트 | 내용 | 근거 |
|---|---|---|
| **I10 구현 선결** | 에피소드 `observed_at` freshness 게이트가 **코드에 없음**(grep 0건; `_freshness_score:484`는 KB chunk 전용, 그조차 비활성). **구현 전 PHR 검진 밴드 배선 금지**(09 "검증할 코드 없으면 테스트 없다") | §3 |
| **측정시점 결합** | 모든 검진 라벨에 "작년 ○월 검진 기준" 분리불가 결합. 검진은 "현재 측정"이 아님 → "특이소견 없음"도 시점 한정. 시점 없는 검진 라벨 출고 0 | §3 |
| **단위 검증** | mg/dL↔mmol/L(공복혈당 7.0 mmol/L=126 mg/dL — 오독 시 당뇨를 "정상"으로). 단위 불일치·미상이면 라벨 금지(M3 confidence 게이트, OCR 단위추출 실패 시 자동 차단) | §4-1 |
| **검사지 참조범위 우선** | OCR 검사지에 기관 참조범위 인쇄 시 **그 값 우선**, 우리 밴드 후순위. 충돌 시 "검사 기관 기준을 따르세요"로 종결 | §4-3 |
| **경계 결정성** | M7 구조화(§3)가 밴드 라벨링의 **절대 선결**. 경계 포함/배제 명시 min/max 없이 lookup 금지 | §4-2 |

---

## 7. 구현 순서 (기획자)

1. **M7 구조화 먼저** — 시드 `bands` 병기(혈압·BMI·혈당 기존 6밴드부터) + migration 011 + 공존 CI. `vital_rules` 결정성의 전제.
2. **출력 라벨 사전 분리** — 중립 3단 사전 + 질환명 명사 게이트(I2 보강). *시드 라벨을 출력에 쓰는 배선 영구 금지.*
3. **시드화 2-A 7종** — 라벨 어휘 중립 상태로 `bands` 추가.
4. **deny-list 2-B 4종 등록** — 라벨 금지 + 비라벨 4축 활용(ack/갭/길안내/일반인용).
5. **I10 에피소드 freshness 구현** — 이게 되기 전 PHR 검진 밴드 주입 배선 금지(선결).
6. **lookup→finding→[R#] 배선** — ref 문서 동반 적재 + cite_doc_id 별칭(§5).

**P1a 통합 검증점(10 §7) 갱신**: 혈압 주의구간이 "📋 내 기록 참고"에 **중립 라벨("관리 권장 구간")**로 + 측정시점 결합 + 원시값 스캔 0 + **질환명("고혈압 1기") 출고 0** — 4개 동시.

---

## 8. 09/10 반영 지시

- [ ] 09 §8: I2를 **I2′(개인귀속 진단 0)**로 교정, 질환명 명사 게이트 추가. I10을 "구현 선결"로 격상.
- [ ] 10 §3-1: "검진수치 11종 시드 확장" → **"2-A 7종 시드 + 2-B 4종 deny-list"**로 정정(eGFR·골밀도·요단백·LDL은 시드 아님).
- [ ] 10 §6: I10에 "에피소드 freshness 미구현(grep 0건) → 배선 선결" 명시. 검사지 참조범위 충돌(I11 보강) 추가.
- [ ] 신규: 출력 라벨 사전 분리를 09 §7(주입 레이어) 정식 규칙으로.
