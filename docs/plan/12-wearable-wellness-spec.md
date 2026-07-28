# 워치(웰니스 등급) 신호 활용 + 교차신호 화이트리스트 (구현 스펙)

> 작성: 2026-06-20 · [10-data-utilization-matrix.md](10-data-utilization-matrix.md) §3-2(웰니스 밴드 신설)·§6 I9(교차신호 화이트리스트) 선결과제를 구현 스펙으로 전개.
> 4관점 3회차(데이터분석가=신호별 웰니스 활용 / 아키텍트=웰니스·임상 분리 구조 / 비평가=의료기기법·유사과학 / 기획자=종합). 웹 검증 출처 첨부.
> 대상 코드: `vital_input.py`(워치 필드 부재), `seed_reference_ranges.py`(SpO2·HR 임상밴드 有), `context_feeds.py`(기저선 TTL 재사용), `migrations/`. **설계만 — 코드 미수정.**

---

## 0. 한 줄 결론 (설계를 또 바꾸는 모순)

비평가가 FDA 근거로 적발: **현 계획(09 §2.1/§4, 10 §6)의 최대 모순은 ECG만 deny하면서 SpO2 임상판정·readiness 합성점수·웰니스 교차신호는 "캐비엇 붙여 활용"으로 열어둔 것.** 그러나 ① SpO2 저산소 판정은 ECG 판독과 **규제 동급**(FDA: 어두운 피부 32% occult 저산소 은폐), ② recovery/strain 점수는 **peer-review 검증 전무한 제조사 마케팅**, ③ 손목 수면추적은 **중증 OSA일수록 정확도 급락**(90%→75%, 가장 위험한 환자에게 가장 강한 거짓안심). → **캐비엇은 위법·유사과학을 합법·과학으로 바꾸지 못한다.** 핵심 교정: deny를 "신호 단위"에서 **"임상 사건 판정 단위"로 재정의**하고, deny ≠ 데이터 거부 = **임상라벨 금지 + 비해석 활용(존재 ack + 의료연계 동선) 짝지음**으로 "하나하나 다 활용"을 위법 0으로 충족.

---

## 1. 핵심 재정의 — deny = "임상 사건 판정 단위"

| 기존(10 §2.1) | 교정 |
|---|---|
| ECG만 deny-list | **deny = {ECG 파형·판독, AFib/불규칙맥 알림 판정, SpO2 저산소 임상판정, 낙상 판정, 제조사 합성점수(readiness/recovery/strain/body battery)}** |

**deny의 정의(비평가 §6)**: "데이터를 안 받는다"가 아니라 **"임상 라벨을 안 붙인다"**. 각 deny 신호에 **비해석 활용 경로를 짝지어** Lv0 방치 0 + 위법 0 동시 달성:

| deny 신호 | 영구 금지 | 허용되는 비해석 활용 |
|---|---|---|
| ECG | 파형·결과·"부정맥" 라벨 | "기기 ECG 기록 존재" ack + 의료진 공유 동선 |
| AFib/불규칙맥 알림 | "부정맥 의심" 판정, 빈도→위험 추정 | "기기 알림 발생 사실" ack + 의료 평가 권고(제조사 라벨 그대로 운반) |
| SpO2 저산소 | "저산소"·"96%=안정" 임상 라벨 | "측정 기록 존재" + 증상 시 의료 측정 권유(피부톤 과대측정 1줄) |
| 낙상감지 | "낙상 위험 높음" 신경학 해석 | 알림 존재 ack + 응급 연락 동선 |
| 제조사 합성점수 | 점수 재생산·의학적 의미 부여·교차 입력 | (가능하면) 존재 인용조차 안 함 |

**규제 근거**: Apple Watch AFib 알림·ECG는 FDA De Novo 개별 클리어이고 라벨에 *"진단용 아님, 임상 판단 지침 사용 금지"*가 박혀 있다 → **제조사조차 진단 못 한다는 출력을 우리가 "해석"하면 라벨 무력화·무면허 SaMD.** 패스스루는 제조사 판정을 그대로 운반할 때만 합법.

---

## 2. 워치 신호별 웰니스 활용 (데이터분석가, 비평가 deny 반영)

**공통 규칙**: 모든 라벨은 "본인 기저선 대비 ±" 또는 "공인 권장 대비"의 **상대 표현**. 임상 컷오프 숫자(60·100·95% 등) 워치 라벨 산출에 미사용. "정상/비정상/안정" 단정 금지.

| 신호 | 웰니스 라벨 | 집계 단위 | 파생지표 | 개인 기저선 최소기간 |
|---|---|---|---|---|
| 수면 총시간 | **가능(근거 최강)** — NSF 권장 7–9h 대비 | 야간 총수면 분, 주간 | 수면부채, 취침 일관성 | 7일 |
| 운동시간 | 가능 — WHO 주150분 대비/본인 대비 | 주간 운동 분·강도구간 | 권장 달성률, 활동 일관성 | 1–2주 |
| 걸음 | 가능(저위험) — 목표/평소 대비 | 일 합·7일 이동평균 | 활동 일관성, 추세 | 7–14일 |
| 안정시 심박 | 가능 — **본인 기저선 대비만**(임상 60–100 금지) | 야간 최저 평균 | 기저선·일일 편차·추세 | 14–30일 |
| 호흡수 | 본인 야간 기저선 대비 추세만 | 야간 평균 | 기저선 편차 | 14일 |
| HRV | **모집단 라벨 불가**(seed:252) — 본인 추세 "참고"만, **교차 입력 제외** | 야간 RMSSD median 1/일 | 회복지표(전일대비) | 14일(기기 교체 시 리셋) |
| 수면 단계 | 단계 판정 금지 — 본인 추세 참고만 | 단계별 분 스칼라 | 수면효율 보조 | 30일 |
| 소모칼로리 | **추정 오차 큼 — 천장 낮음**, 추세 보조만 | 일 총소모 추정 | 활동 일관성 보강 | (보조) |
| **SpO2** | **deny로 이동**(§1) — 임상판정 금지, "재측정/의료 측정 권유"만 | 야간 최저·저하빈도 | (해석 없음) | — |
| **ECG** | **deny** — 판독 금지, 기기 알림 패스스루만 | `device_event` 라벨 | 없음 | — |

**라벨 가능성 위계**: 수면시간(공인 권장 有) ≳ 운동·걸음 > 안정시심박(본인 기저선) > 호흡수·HRV·수면단계·칼로리(본인 추세 참고) >> **SpO2·ECG·낙상·합성점수(deny)**.

---

## 3. 웰니스 vs 임상 분리 구조 (아키텍트)

워치는 임상 `vital_reference_ranges`/`lookup_band`(11)를 **직접 호출하지 않는 별도 경로**. 단 진입점 1개를 공유해 "임상밴드 차단"을 한 곳에서 fail-closed 보장.

**권고: (c) 개인 기저선 기본 + (b) SpO2 한정 별도 테이블, (a) lookup_band 내부분기 기각**
- **부류 W1**(모집단 기준 없음 — HRV·수면효율·활동·호흡수): `wellness_reference` 행 안 만듦(없는 기준 만들면 유사과학) → `personal_baseline`(§4) 대비 추세 라벨만.
- **부류 W2**(SpO2 — 임상밴드 존재하나 워치=웰니스): 임상 `spo2` 행 직접 사용 금지. **deny + 재측정 권유 프레이밍만**(§1).

**단일 접점 — `lookup_band` ①단계 deny 게이트 한 줄**:
```
lookup_band(signal_key, value, *, device_grade, ...):
  ① deny 게이트: signal_key ∈ deny-list  OR  device_grade=='wellness' → match:"denied"
  ②~⑥ 임상 전용 (clinical_near|consumer만 진입)
```
→ **임상 lookup은 워치를 "거부"만 알고, 웰니스 발화는 전혀 모름**(별도 `wellness_rules.run()`). 분리는 물리적(별도 함수·테이블)이되 "워치는 임상밴드 못 씀" 불변식은 한 줄에서 강제(사람이 잊어도 fail-closed). (a) 기각 이유 = 11 §1 "임상↔출력 사전 물리 분리" 정신이 함수 내부에서 무너짐.

---

## 4. 개인 기저선 `personal_baseline` (아키텍트 + 비평가 함정)

**derived 뷰가 아닌 별도 테이블**(스칼라만 → 원시 시계열 물리 분리, I1 구조 보장). `context_feeds.py:42,167` TTL·staleness 패턴 재사용.

```
personal_baseline(user_id, signal_key, window_days, metric,   -- 'ewma'|'rolling_median'
  baseline_value, dispersion, sample_n, device_grade='wellness',
  computed_at,            -- 신선도 게이트(신호별 TTL — HRV 36h 등)
  source_consistency)     -- 윈도 내 device_grade 단일성(혼합 시 강등)
```
- 변동 큰 신호(HRV)는 `rolling_median`(스파이크 강건). 원시 `value` 미저장 → 발화는 상대 라벨(`baseline_lower`)만, 절대 수치(32ms) 출력 0.
- `sample_n < N_min`이면 미발화("평소 패턴 학습 중") — 단일측정 추세 금지(09 §6.2 동형).

**비평가 함정 → 게이트 병행**:
| 함정 | 방어 |
|---|---|
| **병적 기저선**(이미 안정시심박 90인 사람 → "변화 없음=안정"이 만성이상 면죄) | 추세 라벨에 **절대 범위 게이트 병행** — 기저선이 우려 범위면 "안정" 금지, "이 범위는 의료 측정 권고"로 |
| 기기 교체·N 부족 → 단절을 "급변"으로 오인 | **추세 라벨 자동 보류**(기저선 무효 플래그) |
| 느린 병적 악화 → 기저선 함께 떠내려가 은폐("끓는 개구리") | 절대 범위 게이트가 2차 안전망 |

---

## 5. 집계 수신 (M2 — 원시 고해상 금지, 아키텍트)

파트너앱이 **디바이스단에서 집계·이벤트화한 스칼라/라벨만** 수신. 파형·RR배열·hypnogram 키(`rr_intervals`·`ppg`·`ecg_samples`·`hypnogram[]`)가 페이로드에 있으면 **fail-closed 거부**(드롭).

| 신호 | 수신 허용 | 거부 |
|---|---|---|
| HR | 안정시 평균 1/일 | 초단위 스트림 |
| HRV | 야간 median 스칼라 1/일 | RR-interval 배열 |
| 수면 | 총수면·효율·각성수 스칼라(P1c) / 단계별 분(보류 후순위) | 30초 epoch hypnogram |
| 활동 | 일 걸음·활동분 | GPS·가속도 원시 |
| SpO2 | 야간 최저·저하빈도 | 연속 PPG |
| ECG | `record_type='device_event'`(`{device_label:'afib_alert'\|'sinus'\|'inconclusive'}`) | **파형 절대 금지** |

---

## 6. 교차신호 화이트리스트 (I9 — 데이터분석가 W1–W4 + 아키텍트 구조)

**원칙**: 출처 첨부 화이트리스트 조합만. **웰니스 지표(HRV·스트레스·수면단계·readiness)는 교차 입력에서 영구 제외**(무예외 잠금). 제조사 합성점수 용어 재생산 금지.

**데이터구조** (코드 시드 + CI 게이트):
```jsonc
{ "combo_id":"infection.rhr_sleep", "combo":["rhr_baseline_up","sleep_short"],
  "condition":"both_present_within_7d", "device_grade_floor":"wellness",
  "finding_template":"안정시 심박이 평소보다 높고 수면이 짧게 기록되는 패턴입니다 [R#]",
  "cite_doc_id":"ref.wearable_ili.intl", "evidence_required":true,
  "wellness_only":false, "ceiling":"Lv3_shaping_not_diagnosis" }
```
- `evidence_required:true`+`cite_doc_id` → 11 §5 배선: KB 문서 같은 턴 `chunks` 동반적재, 누락 시 **finding 드롭**(출처 없는 조합 *구조적* 발화 불가).
- `wellness_only:true` 조합(순 웰니스)은 등재 자체 금지 → I9 데이터 강제.
- 거버넌스: 코드 시드(`_CROSS_WHITELIST`)만 추가·PR 리뷰, CI 게이트(cite_doc 조인 검증 + 질환명 명사 게이트 11 §1 통과).

**✅ 허용 조합(공인 근거)**:
| # | 조합 | 근거 |
|---|---|---|
| W1 | 야간 안정시심박↑(기저선) + 수면↓ | Fitbit 20만명 코호트 — ILI 조기신호 |
| W2 | 야간 안정시심박↑ + 호흡수↑ | npj Digital Medicine — 감염 초기(1℃↑→HR 8.5bpm↑) |
| W3 | 활동↓ + 수면↓ 지속 | NSF 수면 + WHO 활동 권장(생활습관 일반론) |
| W4 | 안정시심박 기저선 지속 상승(단독·다회) | AHA/ESC — 안정시심박·심혈관 연관(컷오프 없음) |

**❌ 제외(근거 불충분/위법)**: HRV↓+수면↓="번아웃", HRV↓+스트레스↑="만성스트레스", 깊은수면↓+HRV↓="회복부족", 걸음↓+칼로리↓="대사저하", SpO2↓+HRV↓="수면무호흡 의심"(의료기기법), ECG알림+심박↑="부정맥"(deny). **공통원인 인공상관 주의**: 카페인·운동·측정시점·알코올이 여러 지표를 *동시에* 흔듦 → 다지표 동반 변동은 위험 신호가 아니라 단일 생활요인의 그림자.

---

## 7. 출처충돌 + device_grade 무결성 (아키텍트)

신뢰위계 `clinical_near > 공식 PHR > OCR > wellness > 타이핑`. 동일 신호를 워치·Vital기기가 동시 보고 시:
- **등급별 다른 출력 채널**로 충돌 대부분 소거: clinical_near→임상 `lookup_band`, 워치→`personal_baseline`(본인 추세). 워치는 §3 ①단계 wellness deny로 임상 판정에서 빠짐.
- 진짜 충돌(동급 라벨 분기)만 **I11 재측정 권유로 종결**(임의평균·범위제시·침묵폐기 금지).
- **I8 device_grade 무결성**: 페이로드 자기신고 불신 → 파트너앱 **서명 출처 토큰으로 서버가 등급 판정**, 토큰 없음/검증실패 → **wellness 강등** 또는 수신 거부. 위조 clinical_near가 wellness로 강등되면 §3에서 임상 진입 차단 → 위조가 임상 판정으로 못 새어듦. (`vital_input.py:79-114`는 파싱만 — 토큰 검증은 미구현 ingest_server 신규.)

---

## 8. 정확도 고지 = 위험 비대칭 (비평가 §5, §13-3 해소)

"항상 고지"는 경보 피로(양치기 소년), "고지 금지"는 검증된 기기 한계 은폐 → **둘 다 함정**. 해법은 **출력 유형별 비대칭 배분**:
- **안심 방향·임상근접 출력 → 정확도 고지 의무**("이 기기로는 특이소견 없으나 웰니스 기기는 저산소·무호흡을 놓칠 수 있어 증상 시 의료 측정"). 거짓안심이 최악 사고이므로 여기만 강하게.
- **단순 추세·활동 표시 → 고지 최소화**(경보 피로 방지).
- **재측정 권유 → 이유 명시**("측정 흔들림 가능성").

---

## 9. 거짓안심 골든셋 3종 박제 (비평가 §3)

각 시나리오를 명명된 회귀 케이스로:
1. **어두운 피부 SpO2 과대측정** — 실제 88%인데 워치 96% → "특이소견 없음" 금지(occult 저산소 은폐, FDA).
2. **"수면 양호"의 OSA 은폐** — 중증 무호흡 환자에게 워치 효율 88% → 안심 금지(워치가 가장 못 잡는 환자).
3. **HRV 노이즈** — Apple Watch HRV MAPE 28.88% → 노이즈성 하락을 "악화 추세"로 거짓경보 금지.

안심 표현은 "안정/양호" 아니라 **"이 기기로는 특이소견 없음(웰니스 기기 한계 있음, 증상 시 의료 측정 별도)"** 강제.

---

## 10. 09/10/11 반영 지시 + 마이그레이션 정정

- [ ] 10 §2.1·§6: **SpO2를 "밴드 허용"에서 deny로 이동**. deny-list를 "임상 사건 판정 단위"로 재정의(§1). I9에 "웰니스 교차 영구 제외 + 합성점수 용어 금지" 무예외 잠금.
- [ ] 09 §4·§6.4: 워치 교차 자유서술 예시(HR↑+스트레스↑+수면↓) 삭제 → §6 화이트리스트 W1–W4로 대체.
- [ ] 09 §13-3(정확도 고지 미결): **위험 비대칭 고지로 해소**(§8).
- [ ] **마이그레이션 번호 정정(아키텍트 발견 — 코드 확인됨)**: 11 §3.2의 `011_vital_reference_bands.sql`은 `011_conversation_compat.sql`과 **슬롯 충돌**. 임상밴드 = **`012`**, 워치 웰니스(`wellness_reference`·`personal_baseline`·`signal_cross_whitelist`) = **`015`**(013·014 점유). → doc 11 정정 필요.
- [ ] 신규 시드: `wellness_reference`(SpO2 재측정 프레이밍 한정), `personal_baseline`, `signal_cross_whitelist`(W1–W4) — 임상 `vital_reference_ranges`와 물리 분리.

---

## 출처 (웹 검증)
- FDA pulse oximeter 어두운 피부 과대측정·occult 저산소: [FDA Executive Summary](https://www.fda.gov/media/175828/download), [2025 draft guidance](https://www.cnn.com/2025/01/06/health/fda-pulse-oximeters-draft-guidance)
- Apple Watch AFib/ECG "진단용 아님": [FDA De Novo DEN180042](https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN180042.pdf)
- 합성점수(recovery/strain) 검증 전무: [De Gruyter — composite health scores in wearables](https://www.degruyterbrill.com/document/doi/10.1515/teb-2025-0001/html)
- 손목 수면추적 OSA 정확도 급락·HRV MAPE: [PMC sleep tracker vs PSG](https://pubmed.ncbi.nlm.nih.gov/39484805/), [PMC Apple Watch HRV](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11478500/)
- 워치 RHR+수면+호흡수 감염 조기신호(W1·W2): [npj Digital Medicine](https://www.nature.com/articles/s41746-020-00363-7)
- 수면권장 NSF 7–9h: [NSF Sleep Health](https://www.sleephealthjournal.org/article/s2352-7218(15)00015-7/fulltext)
