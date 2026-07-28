# P1a 구현 현황 / 인수인계 (혈압기 수직 관통)

> 작성: 2026-06-20 · /loop 자율 구현 트랙 종료 시점 정리.
> 정본 설계: [14-personalization-consolidated.md](14-personalization-consolidated.md). 본 문서는 그 §6 DAG의 *구현 결과* 기록.
> 상태: **P1a(혈압기 1종 수직 관통) 종단 동작 + 해석 3축 + 안전 골든셋 완료. 전체 556 pass·0 회귀.** P1b(영속화)는 사용자 결정 대기(§5).

---

## 0. 한 줄 요약

원시 측정값(165/105) → **로컬 결정적 해석** → 중립 라벨("경고") → 관련성 게이트 → 안전 블록("기준을 벗어난 구간, 의료진 확인 권장")이 답변에 표시되기까지 **종단 동작**한다. LLM은 원시값도 질환명도 본 적이 없다(경계선 설계의 최강 형태 — 개인 데이터가 프롬프트에 아예 미투입).

---

## 1. 만들어진 것 (커밋 e7832d8 → 523f9a0, 10건)

### 신규 모듈 (전부 순수 함수·결정적·LLM 비의존)
| 파일 | 역할 | 핵심 |
|---|---|---|
| `vital_rules.py` | 해석 엔진(경계선 ②) | `lookup_band`(단일 밴드)·`label_trend`(추세)·`match_cross_signals`(교차 I9)·`run`(vital_input→findings 브리지) |
| `personal_context.py` | 렌더(경계선 ③) | `build`(관련성 게이트 + 밴드·교차 렌더)·`safe_block`(build+C20) |
| `personalization_safety.py` | 안전 게이트 | `find_clinical_labels`(C21 명사구 진단)·`scan_personal_block`/`assert_personal_block_safe`(C20 백스톱) |

### 시드 변경 (`seed_reference_ranges.py`)
- 7개 신호에 기계가독 `bands` 추가(혈압 KR/US clinic+home·혈당·당화혈색소·SpO2·체온·BMI·심박). 자연어 `rule` 불변 → **KB 문서 바이트 동일**(테스트 보장).
- `build_cross_reference_documents`(교차조합 근거 KB) + `metadata.cite_doc_id` 불변 별칭(11 §5).

### 라이브 배선 (★단일 배선점)
- `service_routes.py`: 최신 vital 레코드 → `vital_rules.run` → `generate_response(personal_findings=)`.
- `rag_engine.py` `generate_response`: `+personal_findings=None`(default → **기존 동작 불변**). `emergency_detected` 직후·면책 직전에 `personal_context.safe_block`을 답변에 후append, `not emergency` 가드(I7).

### 구현된 불변식 (정본 14 §3)
| | 강제 지점 | 상태 |
|---|---|---|
| I1 원시값 0 | 개인 데이터 프롬프트 미투입(구조적) + C20 백스톱 | ✅ |
| I2 개인귀속 진단 0 | I12 라벨 분리 + C21 명사 게이트 | ✅ |
| I4 타이핑 미활성 | device 레코드만 run() 입력 | ✅ |
| I5/I7 응급 분리 | not emergency 가드, 매 턴 무상태 재분류 | ✅ |
| I8 deny | device_grade='wellness'/DENY_SIGNALS → denied | ✅ |
| I9 교차 화이트리스트 | match_cross_signals fail-closed + evidence doc | ✅ |
| I11 출처충돌 | lookup 비-ok → finding 미생성 | ✅ |
| I12 라벨 분리 | clinical_label 내부 / label_user 중립 3단 | ✅ |

---

## 2. 검증 (개인화 99 + 전체 556 pass)

| 테스트 | 수 | 핵심 보장 |
|---|---|---|
| `test_vital_rules.py` | 50 | 밴드 정확성(KR/US·AND/OR·보수최댓값)·추세·교차·fail-closed·원시값0·I8 deny·I12 |
| `test_personal_context.py` | 21 | 관련성 게이트(과노출 차단)·중립 렌더·교차 종단·safe_block |
| `test_personalization_safety.py` | 9 | C21 명사구 진단 탐지·C20 백스톱·build↔gate 정합 |
| `test_false_reassurance_golden.py` | 9 | 거짓안심 9벡터 박제(백의/가면 고혈압·워치SpO2·위험값 경고·안심 비대칭) |
| `test_reference_ranges.py` | 12 | KB 본문 불변·cite_doc_id 별칭·I9 evidence_required |

**P1a 종료 게이트(14 §6) 4개 충족**: ①findings 실림 ②중립 라벨 표시 ③프롬프트 원시값 0(구조적) ④질환명 출고 0.

---

## 3. 동작 예시 (종단)

```
입력: vital 레코드 {bps:165, bpd:105, bpm:72}, 질의 "혈압이 높게 나와서 걱정"
 → run(): blood_pressure 경고, heart_rate 안정 (findings, 원시값 없음)
 → build(): 질의 scope=혈압 → 혈압만 표면화(심박 드롭)
 → safe_block(): C20 통과
 → 답변 끝에 append:
     ## 📋 내 기록 참고
     - 최근 측정된 혈압은(는) 기준을 벗어난 구간으로, 의료진 확인이 권장됩니다.
     측정값의 해석과 진단은 의료진과 상담하세요.
 LLM 프롬프트에 165·105·"고혈압"은 전혀 등장하지 않음.
```

---

## 4. 아직 안 된 것 (P1b+, 결정/소스 대기)

| 항목 | 막힌 이유 |
|---|---|
| **영속화**(`consent_ledger`·`personal_measurement`, migration 015/016) | §5 결정 선행 |
| **추세 실표시**(`label_trend` 엔진은 완성) | 측정 *이력* 필요 → 영속화 |
| **교차 대사조합 실발화**(매처·근거 KB 완성) | 체중계 BMI 수신 필요 → 소스 연동 |
| **인용 `[R#]` 동반적재**(현재 블록은 마커 없이 append) | citation 배선 증분 |
| **가정혈압 정상 tier**(현재 역치만 — 미만 no_match) | 추가 시드(거짓안심 비대칭상 현 상태도 안전) |
| **워치 wellness_rules / PHR record_surface / OCR** | 소스 연동 + P1c |

---

## 5. 다음 진전을 막는 결정 (14 §8 — 사용자 입력 필요)

1. **디바이스 연동 방식** — 파트너앱 push(유력) / 헬스플랫폼(Apple Health·삼성헬스) / 직접 SDK. → `ingest_server` 계약·`personal_measurement` 수신 형태를 가름.
2. **PHR 출처** — 공단·심평원 직접(인증·국외이전 난이도↑) / 파트너앱 보유분. → consent·민감정보 처리 범위를 가름.
3. (부) **국외이전 동의 모델** — 현재 개인 데이터가 LLM 프롬프트 미투입이라 *라벨조차 국외 미전송*. consent_ledger 설계 시 이 강한 경계가 동의 부담을 낮춤.

→ **1·2 결정 시 P1b 영속화를 설계·구현 가능.** P1a 해석/렌더 엔진은 그대로 재사용(인메모리 시드 → DB lookup만 교체).

---

## 6. 재현 / 검증 방법
```
python -m pytest tests/test_vital_rules.py tests/test_personal_context.py \
  tests/test_personalization_safety.py tests/test_false_reassurance_golden.py -q
# → 89 pass (+ test_reference_ranges 12). 전체: python -m pytest tests/ -q → 556 pass.
```
라이브 경로는 PG 필요(`service_routes` SSE). 개인화 로직은 전부 순수 함수라 DB 없이 검증됨.
