# 개인화 의료 RAG 플랫폼 — 목표 아키텍처 설계서

> 작성: 아키텍트 역할 에이전트 (2026-06-11) · 검토 전 초안

**대상 리포**: `medical-rag-service`
**전제**: 1~3인 팀, GCP Cloud Run + Cloud SQL PostgreSQL 15(pgvector), 의료법 준수 최우선, 글로벌 확장 감안

---

## 0. 요약 (Executive Summary)

본 설계의 핵심 명제는 세 가지다.

1. **"GPT/Gemini보다 낫다"의 정의를 모델 성능이 아니라 *맥락·근거·안전*으로 잡는다.** 범용 LLM은 사용자의 혈압 추세, 복용 약, 집안 CO₂를 모른다. 우리는 (a) 검증된 KB 인용 강제(이미 구현됨: `evidence_pack.py`의 `must_cite_every_medical_claim`), (b) 개인 컨텍스트(생체신호·PHR·공기질)의 **규칙 기반 해석 결과** 주입, (c) DUR·KDCA 등 한국 공공 근거 우선순위로 차별화한다. LLM은 "해석자"가 아니라 "규칙 엔진 산출물과 인용 근거의 서술자"로 격하시킨다.
2. **SaMD(의료기기 소프트웨어) 경계를 아키텍처 수준에서 강제한다.** 개인화가 깊어질수록 "정보 제공"과 "진단·처방"의 경계가 흐려진다. 경계 판정을 사람의 문구 검토에 맡기지 않고, 관할(jurisdiction)별 기능 플래그 + 규칙 엔진의 결정적(deterministic) 출력 + LLM 자유 해석 금지 제약으로 코드에 박는다.
3. **현 코드베이스는 "교체"가 아니라 "둘러싸기(strangler)" 대상이다.** `medical_rag_pipeline.py`의 단계 구조(PII→분류→안전분기→라우팅→검색→Evidence Pack→생성→인용검증→리뷰큐→감사)는 의존성 주입식으로 잘 설계되어 있어 그대로 유지·확장한다. 교체 대상은 `rag_server.py`의 stdlib HTTP 계층과, 새로 추가되는 수집(ingest) 경로뿐이다.

---

## 1. 목표 아키텍처

### 1.1 설계 원칙

| # | 원칙 | 근거 |
|---|------|------|
| P1 | **개인 데이터 해석은 규칙 엔진만, LLM은 서술만** | 의료법 제27조(무면허 의료행위 금지) 리스크 차단. LLM의 비결정적 해석은 감사·재현이 불가능 → 규칙 엔진은 버전·임계값·출처가 감사 가능 |
| P2 | **개인 컨텍스트와 의료 근거(KB)의 분리** | Evidence Pack에서 `[E#]`(KB 인용)과 `[R#]`(규칙 엔진 판정)을 네임스페이스로 분리. 개인 데이터는 "근거"로 인용될 수 없음 |
| P3 | **수집(ingest)과 질의(query)의 경로 분리** | 생체신호/IoT는 쓰기 중심·고빈도, RAG 질의는 읽기 중심·저빈도. 장애 격리와 스케일 특성이 다름 |
| P4 | **리전 고정(region-pinned) 개인 데이터, 글로벌 공유 KB** | 개인정보보호법 제28조의8(국외 이전), GDPR 제44~49조. KB(비개인 공공자료)는 리전 간 복제 가능 |
| P5 | **모든 단계 멱등·추가적(additive) 변경** | 현 리포의 마이그레이션 규율(`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`) 유지 — 1~3인 팀에서 롤백 가능성이 생존 조건 |

### 1.2 논리 구성도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ① 데이터 수집 레이어 (Ingestion)                                              │
│                                                                              │
│  [모바일 앱]                     [마이헬스웨이/병원]        [집안 IoT 센서]      │
│   Apple HealthKit                 FHIR R4 (KR Core)        PM2.5/CO2/VOC     │
│   Android Health Connect          OAuth2 + 전송요구권        온습도            │
│   수동 입력(혈압계 등)              Bulk/단건 조회             │                │
│        │                              │                     │ MQTT(TLS)      │
│        ▼                              ▼                     ▼                │
│   POST /api/ingest/vitals      PHR Sync Worker         MQTT Bridge          │
│   (FastAPI, 신뢰헤더 인증)        (Cloud Run Job/스케줄)   (EMQX/HiveMQ Cloud)  │
│        │                              │                     │ → Pub/Sub      │
│        └──────────────┬───────────────┴─────────────────────┘                │
│                       ▼                                                      │
│              ┌──────────────────┐                                            │
│              │ Ingest Pipeline   │  단위 정규화(UCUM) · LOINC 매핑              │
│              │ (검증·정규화·중복  │  이상치/센서아티팩트 필터                      │
│              │  제거·동의 확인)   │  ★동의 원장 조회 — 동의 없으면 DROP           │
│              └────────┬─────────┘                                            │
└───────────────────────┼──────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ② 개인 컨텍스트 스토어 (Personal Context Store) — 리전 고정                     │
│                                                                              │
│  Cloud SQL PostgreSQL 15 (기존 인스턴스, 스키마 분리: personal.*)              │
│  ├─ phr_observations    : 시계열 원본 (월별 파티션, LOINC+UCUM+FHIR JSONB)    │
│  ├─ env_observations    : 공기질 시계열 (device_id, 월별 파티션)               │
│  ├─ phr_conditions      : 진단 이력 (KCD-8/ICD-10/SNOMED CT)                 │
│  ├─ phr_medications     : 투약 이력 (ATC/KD코드 — DUR 교차조회용)              │
│  ├─ user_health_snapshot: 사용자별 최신값+추세 (1행/사용자, UPSERT)            │
│  ├─ consent_ledger      : 동의 원장 (append-only, 목적·버전·철회)              │
│  └─ personal_audit_log  : 개인 데이터 접근/사용 감사                           │
└───────────────────────┬──────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ③ 규칙 기반 레드플래그 엔진 (Deterministic Rule Engine)                        │
│    packages/medical_shared/vital_rules (compliance_rules와 동급 신규 패키지)   │
│                                                                              │
│  입력: snapshot + 최근 시계열     출력: findings[] (rule_id, severity, 출처)   │
│  예) SBP≥180 또는 DBP≥120  → EMERGENCY  "고혈압 위기 범위" (ACC/AHA 2017)     │
│      SpO2≤90%             → EMERGENCY  (WHO 산소요법 기준)                    │
│      체온≥38 + 영아<3개월   → URGENT    (대한소아과학회/NICE NG143)             │
│      CO2>1,000ppm         → ADVISORY  환기 권고 (실내공기질 관리법 기준 준용)   │
│      PM2.5>35µg/m³        → ADVISORY  민감군 주의 (환경부 CAI '나쁨' 기준)     │
│  특성: 버전 관리(rule_version) · 히스테리시스 · 데이터 신선도 창 · 단위 검증      │
│  ★ EMERGENCY findings → 기존 응급 분기(_EMERGENCY_MSG, 119 안내)와 동일 경로    │
└───────────────────────┬──────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ④ 개인화 RAG 파이프라인 (기존 medical_rag_pipeline.py 확장)                    │
│                                                                              │
│  PII마스킹 → 분류 → ★개인컨텍스트 결합(밴딩·추상화) → 안전 사전점검(위기/응급      │
│  + ★레드플래그 findings 병합) → 라우팅(intent×관할) → Hybrid Search(기존        │
│  RRF+리랭크) → Evidence Pack(★personal_context 블록 주입) → 생성(GPT-5/        │
│  지역별 프로바이더) → 인용 검증([E#]+[R#]) → 가드레일 → 리뷰 큐 → 감사 로그       │
└───────────────────────┬──────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⑤ 안전/컴플라이언스 파이프라인 (횡단 관심사)                                     │
│  · 관할별 기능 플래그(jurisdiction_features) — SaMD 경계 강제                   │
│  · 동의 게이트(질의 시점 재확인) · PII 최소화(밴딩 후 전송)                       │
│  · rag_queries 감사 확장: personal_context_hash, rule_version, consent_ref    │
│  · 리뷰 큐(기존 review_queue_items) + 개인화 답변 표본 검수                     │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ⑥ 글로벌 멀티리전 토폴로지                                                      │
│                                                                              │
│   KR (asia-northeast3)          EU (europe-west4)        US (us-central1)    │
│   ┌──────────────────┐          ┌──────────────────┐    ┌────────────────┐  │
│   │ 개인 스토어(고정)   │          │ 개인 스토어(고정)   │    │ 개인 스토어(고정)│  │
│   │ KB 마스터(원본)    │──복제──▶ │ KB 리드 레플리카    │    │ KB 리드 레플리카 │  │
│   │ LLM: OpenAI/      │          │ LLM: EU 리전       │    │ LLM: US 리전    │  │
│   │  Vertex(서울)      │          │  엔드포인트         │    │  엔드포인트      │  │
│   └──────────────────┘          └──────────────────┘    └────────────────┘  │
│   원칙: 개인 데이터는 가입 리전을 벗어나지 않음. KB(비개인)만 단방향 복제.           │
│   라우팅: 가입 시 리전 결정 → 사용자-리전 매핑은 글로벌 디렉터리(개인정보 미포함)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 컴포넌트별 설계 요점

**① 수집 레이어**
- **모바일 생체신호**: HealthKit/Health Connect은 서버 푸시가 아니라 *기기 내 저장소*다. 앱이 주기적으로(백그라운드 작업) 델타를 읽어 `POST /api/ingest/vitals`로 배치 전송하는 구조가 현실적. 서버는 `(user_id, loinc_code, effective_at, source)` 유니크 제약으로 멱등 수신.
- **마이헬스웨이(PHR)**: 보건복지부 의료 마이데이터 중계 플랫폼. 본인 인증·전송요구(개인정보보호법 2023 개정으로 도입된 전송요구권 기반) 후 FHIR R4 / KR Core 프로파일로 진료·투약·검진 데이터를 수신. **사용자 주도 동기화(사용자가 버튼을 눌러 가져옴)**로 시작 — 상시 폴링은 동의·세션 관리 부담이 1~3인 팀에 과함.
- **IoT 공기질**: 가정 내 센서는 NAT 뒤에 있으므로 서버로의 직접 HTTP보다 **MQTT(TLS, 기기별 인증서/토큰)** 가 표준. 단, 자체 브로커 운영은 팀 규모에 비해 무겁다 → 관리형 브로커(EMQX Cloud/HiveMQ Cloud) → webhook/Pub/Sub → Cloud Run 수신 워커. 초기에 제휴 센서가 1~2종이면 제조사 클라우드 API 폴링이 더 싸다(트레이드오프 §6.1).

**② 개인 컨텍스트 스토어** — 별도 DB 인스턴스가 아니라 **기존 Cloud SQL에 PostgreSQL 스키마(namespace) 분리**(`personal.*` vs 기존 `public.*`)로 시작한다. 이유: (a) 팀 규모상 인스턴스 추가는 운영 부담, (b) 권한 분리는 스키마 단위 GRANT로 충분히 시작 가능, (c) 향후 인스턴스 분리 시 `pg_dump --schema=personal`로 깨끗하게 이전 가능. 시계열 설계는 §3.3.

**③ 레드플래그 엔진** — 핵심 차별화이자 법적 방어선. 모든 규칙은 (임계값, 공식 출처, 권고 문구 템플릿, severity)의 4튜플로 선언하고 `packages/medical_shared`(이미 git submodule로 분리된 공유 패키지)에 둔다. 기존 `consultation_checklists`의 red_flag 부스트(`rag_engine.py`의 `apply_red_flag_boost`)가 *검색 랭킹*용이라면, 이 엔진은 *수치 데이터 판정*용 — 역할이 다르므로 별도 모듈로 하되 같은 패키지에 둔다. EMERGENCY 판정은 기존 `medical_rag_pipeline.py`의 emergency 분기(`_EMERGENCY_MSG`, 119 안내)와 동일한 출구로 합류시켜 안전 경로를 일원화한다.

**④ 개인화 RAG** — Evidence Pack 확장이 유일한 구조 변경점이다 (§5.1에 스키마). `build_evidence_pack()`의 `answer_constraints`에 `must_not_interpret_personal_data_beyond_findings: true`를 추가하고, `citation_verifier.py`를 `[R#]`(규칙 판정 인용)도 검증하도록 확장한다.

**⑥ 멀티리전** — "글로벌 서비스"의 최소 실행 가능 형태는 *리전별 풀스택 복제 + 개인 데이터 고정*이다. 사용자→리전 매핑 디렉터리(이메일 해시→리전 코드만 보관, 개인정보 비포함)만 글로벌이다. KB는 비개인 공공자료이므로 자유 복제 가능하나, **KB 콘텐츠 자체가 관할 종속적**(KDCA/심평원 근거는 KR 전용, NICE는 UK/EU 참고)이라는 점이 더 중요 — `kb_sources.jurisdiction` 컬럼(009 마이그레이션에 이미 존재)을 리전별 검색 필터로 활용한다.

---

## 2. SaMD(의료기기 소프트웨어) 경계 아키텍처

### 2.1 관할별 규제 프레임

| 관할 | 기준 문서 | 비의료기기(웰니스)로 남는 조건 | 의료기기로 넘어가는 트리거 |
|------|----------|------------------------------|--------------------------|
| **한국 (식약처)** | 「의료기기와 개인용 건강관리(웰니스) 제품 판단기준」(식약처 가이드라인), 의료기기법 제2조 | 사용목적이 *일상적 건강관리*(체력 증진, 건강정보 제공) 또는 *만성질환 자가관리 보조*이고, 위해도가 낮을 것. 판단의 1차 기준은 **표방하는 사용목적(intended use)** | "질병의 진단·치료·경감·처치·예방" 목적 표방. 예: 측정 혈압으로 고혈압을 *진단*, 특정 약 복용을 *지시*, 부정맥 *판정* |
| **미국 (FDA)** | General Wellness: Policy for Low Risk Devices(2019), FD&C Act §520(o)(1)(E) + CDS Software Guidance(2022.9) | (a) 일반 웰니스 주장(건강한 생활습관과 만성질환 위험 감소의 *일반적* 연관 언급까지 허용) + 저위험. (b) CDS 예외는 **의료인 대상**일 때만 — §520(o)(1)(E)(iii) | **환자 대상(patient-facing)** 의사결정 지원은 CDS 예외 불가. 신호(signal) 취득·분석(생체신호 패턴 분석으로 질병 탐지)은 예외 제외 |
| **EU** | MDR 2017/745 Rule 11, MDCG 2019-11 (소프트웨어 자격·분류) | 의료 목적이 없는 라이프스타일/웰빙 소프트웨어 (MDR Recital 19) | "진단·치료 목적의 의사결정에 사용되는 정보를 제공"하는 소프트웨어는 **최소 Class IIa**. Rule 11은 경계가 매우 낮음 — 증상 기반 트리아지 앱도 MDSW로 판정된 사례 다수 (MDCG 2019-11 §3) |
| **참고 (영국)** | MHRA "Medical device stand-alone software including apps" | 단순 정보 제공·기록 | 증상 체커/트리아지가 개인별 결과를 내면 의료기기 가능성 |

**핵심 통찰**: 세 관할 모두 판정 기준은 코드가 아니라 **표방하는 사용목적과 출력 문구**다. 따라서 경계 통제는 (1) 출력 문구 템플릿의 중앙 관리, (2) 관할별 기능 차단, (3) 마케팅 문구 통제의 세 층이 모두 필요하다.

### 2.2 기능별 경계 판정표

| 기능 | KR | US | EU | 판정 근거와 설계상 처리 |
|------|----|----|----|------------------------|
| 생체신호 기록·시각화·추세 표시 | 웰니스 | 웰니스 | 비MDSW | 단순 기록/표시는 전 관할 안전. 단, "이상 감지" 워딩 금지 |
| 공기질 정보 + 환기 권고 | 웰니스 | 웰니스 | 비MDSW | 환경 정보이며 의료 판단 아님. 환경부/WHO 기준 인용으로 제공 |
| 일반 건강정보 RAG(현 서비스) | 웰니스(정보제공) | 웰니스 | 경계 주의 | 개인 무관 공공 건강정보 + 인용. EU에서는 개인 증상 입력→답변 구조가 Rule 11 회색지대 → EU 출시 시 문구·기능 보수화 필요 |
| **레드플래그 안내** (SBP≥180 → "응급실 안내") | **경계(회색)** | 경계 | **MDSW 가능성 높음** | 개인 측정값 기반 행동 안내는 트리아지 성격. 방어 설계: ① 공인 임계값을 *그대로* 인용(자체 알고리즘 아님) ② "진단이 아니며 일반 안전정보" 명시 ③ 보수적 방향으로만 오류(과소경고 금지) ④ KR/US 우선 출시, EU는 인증 전 비활성 |
| 투약 이력 × DUR 병용금기 *정보 표시* | 경계 | 경계 | MDSW 가능성 | "병용금기로 *등재된 정보가 있음* → 약사 상담" 수준의 공공 DB 사실 전달로 한정. 용량 조절·복용 중단 권고는 절대 금지(처방 행위) |
| 증상+생체신호 결합 *진단 추정* | **의료기기** | **의료기기** | **MDSW Class IIa+** | **구현 금지** (기존 `must_not_diagnose` 제약 유지). 향후 사업적으로 원하면 정식 SaMD 인허가 트랙(§2.4) |
| 만성질환(고혈압 등) 자가관리 코칭 | 웰니스(식약처 판단기준의 만성질환 자가관리 유형) | 일반 웰니스 주장 범위 내 | 경계 | "의사가 진단한 고혈압의 생활관리"는 웰니스 가능. "혈압약을 바꿔라"는 불가 |

### 2.3 관할별 기능 플래그 설계

```sql
-- migrations/0XX_jurisdiction_features.sql (멱등 규율 유지)
CREATE TABLE IF NOT EXISTS jurisdiction_features (
    jurisdiction   TEXT NOT NULL,     -- 'KR' | 'US' | 'EU' | 'DEFAULT'
    feature_key    TEXT NOT NULL,     -- 'red_flag_vitals' | 'dur_cross_check'
                                      -- | 'phr_context' | 'env_advisory' ...
    enabled        BOOLEAN DEFAULT FALSE,   -- ★ 기본 OFF (deny-by-default)
    constraint_json TEXT DEFAULT '{}',-- 관할별 문구 템플릿 ID, 보수화 수위
    reviewed_by    TEXT,              -- 규제 검토자 (수동 승인 흔적)
    reviewed_at    TIMESTAMPTZ,
    PRIMARY KEY (jurisdiction, feature_key)
);
```

- **deny-by-default**: 매핑이 없으면 기능 OFF. 신규 관할 진출 시 "검토 완료된 기능만 켜는" 구조.
- 파이프라인 주입 지점: `medical_rag_pipeline.process_medical_query()`에 `jurisdiction` 파라미터 추가 → 개인 컨텍스트 결합·레드플래그·DUR 교차조회 각 단계가 플래그를 조회. **사용자 계정의 가입 리전**을 신뢰 소스로 사용(질문 언어로 관할을 추정하면 오판).
- 출력 문구 템플릿도 관할 키로 분리: EU용은 더 보수적 문구를 쓸 수 있게 `constraint_json`에 템플릿 ID를 둔다.

### 2.4 경계 유지를 위한 구조적 장치

1. **의도된 사용목적 문서(Intended Use Statement)를 리포에 버전 관리** — 모든 신규 기능 PR은 이 문서와의 정합 체크를 통과해야 함.
2. **출력 계층 분리**: 규칙 엔진 findings는 "사전 승인된 문구 템플릿 + 출처 인용"만 출력. LLM은 findings를 *재배열·연결*할 수 있으나 *새 의학적 판단을 추가할 수 없음*.
3. **향후 SaMD 트랙 대비**: 레드플래그 엔진을 의도적으로 결정적·버전화·단위테스트 완비 상태로 유지하면, 추후 식약처 2등급 SaMD 인허가(또는 FDA De Novo/510(k))로 가는 경우 IEC 62304·ISO 14971 문서화의 기술적 토대가 된다. **지금 웰니스로 출시하되, 의료기기 전환 비용을 낮추는 설계**다.

---

## 3. 데이터 플랫폼

### 3.1 FHIR 리소스 매핑

마이헬스웨이가 FHIR R4 / KR Core를 채택하고 있으므로 내부 표현도 FHIR 정합으로 설계하되, **풀 FHIR 서버를 운영하지 않는다**. "타입드 컬럼 + 원본 FHIR JSONB 보존"의 이중 표현을 쓴다.

| 수집 데이터 | FHIR 리소스 | 핵심 코드 체계 | 내부 테이블 |
|------------|------------|---------------|------------|
| 혈압 | `Observation` (vital-signs, component 2개) | LOINC 85354-9(패널), 8480-6(수축기), 8462-4(이완기), UCUM `mm[Hg]` | `phr_observations` |
| 체온 | `Observation` | LOINC 8310-5, UCUM `Cel` | 〃 |
| 산소포화도 | `Observation` | LOINC 59408-5, UCUM `%` | 〃 |
| 심박/스트레스(HRV) | `Observation` | LOINC 8867-4(심박), HRV는 표준 부재 → 자체 코드 + `device_id` 필수(웰니스 지표로만) | 〃 |
| 진단 이력 | `Condition` | **KCD-8** ↔ SNOMED CT 매핑 | `phr_conditions` |
| 투약 이력 | `MedicationStatement`/`MedicationRequest` | **ATC** + **KD코드/보험EDI**(기존 DUR KB와 조인 키) | `phr_medications` |
| 검진 결과 | `Observation`/`DiagnosticReport` | LOINC | `phr_observations` |
| 알레르기 | `AllergyIntolerance` | KCD/SNOMED | `phr_conditions`(category 구분) |
| 공기질 | FHIR 표준 없음 → `Observation` 변형 | 자체 코드(`env:pm25`, `env:co2`, `env:tvoc`) + UCUM | `env_observations` |
| 동의 | `Consent` | — | `consent_ledger` (FHIR Consent export 가능 형태) |

- **원본 보존 원칙**: FHIR Bundle은 `fhir_json JSONB`로 무손실 보관, 타입드 컬럼은 파생. 매핑 버그 발견 시 재파생 가능(기존 `reembed` 패턴과 동일 사상).
- **투약 이력 × DUR**: 기존 DUR 시드와 KD코드/성분코드로 조인 → "복용 중인 약 기준 병용금기 *정보 존재 여부*" — 범용 LLM이 흉내 낼 수 없는 가장 강한 차별화 포인트(§2.2 문구 한계 준수).

### 3.2 표준 용어 체계 전략

| 체계 | 용도 | 도입 시점 |
|------|------|----------|
| LOINC + UCUM | 생체신호·검사 식별과 단위 정규화. **수집 시점에 강제** | 0-3개월 (필수) |
| KCD-8 | 국내 진단 코드 | 3-6개월 (PHR 연동과 동시) |
| ATC + KD코드 | 약물 — DUR 조인의 전제 | 3-6개월 |
| SNOMED CT | 글로벌 확장 시 KCD↔SNOMED 매핑(KOSTOM 매핑표) | 6-12개월 |

### 3.3 시계열 저장 선택지 트레이드오프

전제 수치: 사용자 1만 명, 생체신호 10건/일 + 공기질 센서 1대(5분 간격) ≈ 연간 약 11억 행(공기질 지배적). 공기질은 5분→15분 다운샘플링 + 원본 30일 보존 정책으로 1/10 절감 가능.

| 선택지 | 장점 | 단점 | 판정 |
|--------|------|------|------|
| **Cloud SQL PG15 + 네이티브 파티셔닝(월별) + 집계 테이블** | 운영 대상 추가 0개. 동의 원장·RAG와 동일 DB 조인 | 압축 없음 → 스토리지 증가(예측 가능) | **✅ 0-12개월 권고안** |
| TimescaleDB | 압축(10~20×)·continuous aggregate | **Cloud SQL 미지원** → 운영 대상 +1 | 보류 |
| BigQuery | 무한 스케일, 저장 비용 저렴 | 최신값 조회 부적합(OLAP) | **콜드 계층만**(90일+, 6-12개월) |
| Bigtable/InfluxDB | 고빈도 IoT 최적 | 운영 복잡도, 조인 불가 | 제외 |

**권고 스키마 골격**:

```sql
CREATE TABLE personal.phr_observations (
    user_id      TEXT NOT NULL,
    loinc_code   TEXT NOT NULL,
    value_num    NUMERIC,
    value_text   TEXT,
    unit_ucum    TEXT,
    effective_at TIMESTAMPTZ NOT NULL,
    source       TEXT NOT NULL,        -- 'healthkit'|'health_connect'|'myhealthway'|'manual'
    device_id    TEXT,
    quality_flag TEXT DEFAULT 'ok',    -- 'ok'|'artifact_suspect'|'out_of_range'
    fhir_json    JSONB,
    created_at   TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, loinc_code, effective_at, source)  -- 멱등 수신
) PARTITION BY RANGE (effective_at);

CREATE TABLE personal.user_health_snapshot (
    user_id    TEXT PRIMARY KEY,
    metrics    JSONB NOT NULL,   -- {"8480-6": {"v":142,"u":"mm[Hg]","at":"...","trend_7d":"+5"}}
    env        JSONB,            -- {"pm25": {...}, "co2": {...}}
    updated_at TIMESTAMPTZ
);
```

스냅샷은 ingest 트랜잭션에서 동기 UPSERT(읽기 경로에서 시계열 스캔 제거 — RAG 질의 레이턴시 보호).

### 3.4 동의(Consent) 원장

법적 근거: 개인정보보호법 제15조·**제23조(민감정보 — 건강정보는 별도 동의 필수)**·제28조의8(국외 이전 동의), GDPR 제9조(2)(a), 제7조(동의 입증 책임).

```sql
CREATE TABLE personal.consent_ledger (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    purpose         TEXT NOT NULL,    -- 'vitals_collection'|'phr_sync'|'env_collection'
                                      -- |'personalized_answers'|'llm_processing'|'cross_border'
    scope_json      TEXT NOT NULL,    -- 데이터 항목 단위 (예: ["BP","SpO2"])
    policy_version  TEXT NOT NULL,    -- 동의서 문안 버전 (입증 책임 대응)
    action          TEXT NOT NULL,    -- 'granted' | 'revoked'
    granted_at      TIMESTAMPTZ NOT NULL,
    evidence_json   TEXT              -- UI 화면 ID, IP, 인증 수단 (입증용)
);  -- append-only: UPDATE/DELETE 권한을 앱 롤에서 제거
```

- **목적 단위 분리 동의**: "수집" / "개인화 답변 활용" / "외부 LLM 처리(국외 이전)"는 별개 목적 — 별도 항목으로 받는다.
- **철회 전파**: revoke 시 (a) 이후 수집 즉시 차단, (b) 기존 데이터 파기 또는 분리 보관(제21조), (c) 개인화 RAG 즉시 비개인화 모드 폴백. 질의 시점마다 동의 캐시(수 분 TTL) 확인.
- 모든 개인화 답변의 감사 레코드에 `consent_ref` 기록.

### 3.5 암호화·가명화

| 층 | 조치 | 근거 |
|----|------|------|
| 저장 | Cloud SQL CMEK + 민감 컬럼 애플리케이션 레벨 AES-GCM 봉투 암호화(레드플래그 평가용 `value_num`은 평문 유지 + 식별자 분리 절충 가능) | 개인정보보호법 시행령 제30조·안전성 확보조치 기준, HIPAA §164.312(a)(2)(iv) |
| 식별자 분리 | `user_id`는 인증계와 무관한 난수 UUID. 실명·연락처는 호스트 인증계에만(현 구조 그대로) | 제28조의2(가명처리), GDPR Art.4(5) |
| 전송 | TLS 1.2+, MQTT는 기기별 자격증명 + mTLS | 안전성 확보조치 기준 |
| LLM 전송 | §5.1 밴딩·최소화 + zero-retention 옵션 + 리전 엔드포인트 | 제28조의8, GDPR 제44조 |

### 3.6 데이터 거주성·관할 대응

| 관할 | 요구 | 설계 대응 |
|------|------|----------|
| 한국 | 국외 이전 시 고지·동의(제28조의8). 본인 전송요구로 받은 PHR은 PIPA 체계 | 개인 스토어 서울 고정. 국외 LLM 전송은 별도 동의 + 마스킹·밴딩 |
| EU | GDPR 이전 메커니즘(제44~49조, SCC). EU→한국은 2021년 적정성 결정 | EU 가입자는 `europe-west` 스택. LLM은 EU 리전 엔드포인트. DPIA 수행 |
| 미국 | DTC 웰니스 앱은 HIPAA 비대상 — FTC Health Breach Notification Rule, 주법(WA My Health My Data 등) | 판매·광고 목적 사용 금지 명시, 유출 통지 절차 |
| 공통 | — | 사용자-리전 매핑만 글로벌, 리전 간 이동은 "사용자 명시 요청 이주"만 |

---

## 4. 현재 코드베이스에서의 진화 경로

### 4.1 유지 / 확장 / 교체 판정

| 자산 | 판정 | 내용 |
|------|------|------|
| `medical_rag_pipeline.py` | **유지+확장** | `process_medical_query()`에 `personal_context`, `jurisdiction` 파라미터 추가 |
| `evidence_pack.py` | **확장** | `personal_context` 블록 + `answer_constraints` 추가. E1~E8 불변 |
| `rag_engine.py` hybrid_search | **유지** | 개인화는 쿼리 확장 + `evidence_topic` 필터로만 — 랭킹 코어 무변경 |
| `pii_masker.py` | **확장** | 수치 밴딩과 결합 |
| `retrieval_router.py` | **확장** | intent 추가, 관할별 라우팅 테이블 분기 |
| `citation_verifier.py`, `review_queue.py` | **확장** | `[R#]` 검증, 개인화 답변 검수 우선순위 상향 |
| `packages/medical_shared` | **확장** | `vital_rules` 모듈 신설 |
| migrations 체계 | **유지** | `personal.*` 스키마도 동일 규율 |
| `rag_server.py` (stdlib) | **단계적 교체** | §4.2 스트랭글러 |
| `config.py`의 SKIX 설정 잔재 | **정리** | 레거시 흔적 분리 |
| 듀얼 임베딩 컬럼(BGE-M3 예약) | **유지** | 글로벌 다국어 확장 시 그대로 활용 |

### 4.2 stdlib HTTP 서버의 한계와 전환 시점

한계: ① 요청 검증 부재(Pydantic 필요) ② 스레드-퍼-요청 동시성(SSE+ingest에서 고갈) ③ OpenAPI 부재 ④ 횡단 관심사 미들웨어 부재.

**전환 전략 — 빅뱅 금지, 스트랭글러 2단계**:
- **1단계 (0-3개월)**: 신규 경로만 FastAPI — `ingest_server.py`를 별도 Cloud Run 서비스로 신설(`/api/ingest/*`, `/api/consent/*`). 기존 `rag_server.py` 무변경. 신뢰헤더 인증을 FastAPI dependency로 이식.
- **2단계 (3-6개월)**: RAG 서비스 전환 — `RagRoutesMixin` 핸들러를 FastAPI 어댑터로 호출, 엔드포인트 단위 이전(SSE는 `StreamingResponse`) → 트래픽 전환 후 폐기.

### 4.3 소규모 팀(1~3인) 현실 반영 원칙

- **서비스 수 상한 3개**: 호스트 프록시 / RAG+ingest / 배치(Cloud Run Jobs).
- **운영형 인프라 추가 금지 목록**: 자체 MQTT 브로커, 자체 FHIR 서버, Kafka, K8s.
- **기존 운영 자동화 자산(마이그레이션 러너·시드·gap 루프)을 개인 스토어에도 그대로 적용.**

---

## 5. 개인화 안전 설계

### 5.1 개인 데이터의 LLM 프롬프트 주입 — PII 최소화

원칙: **LLM에는 "원시값"이 아니라 "규칙 엔진이 판정한 밴드·추세·findings"만 전달한다.**

Evidence Pack 확장 스키마:

```json
{
  "personal_context": {
    "provenance": "PERSONAL_RULE_ENGINE",
    "rule_version": "vital-rules-2026.06",
    "profile_bands": {
      "age_band": "40대", "sex": "F",
      "conditions_categories": ["고혈압(진단 이력 있음)"],
      "medications_atc_classes": ["C09A (ACE억제제 계열)"]
    },
    "findings": [
      {"finding_id": "R1", "rule_id": "bp.sbp.stage2",
       "statement": "최근 7일 수축기 평균이 2단계 고혈압 범위(140-159mmHg)에 해당",
       "source": "ACC/AHA 2017 / 대한고혈압학회 2022 진료지침",
       "severity": "advisory", "data_freshness": "3h"},
      {"finding_id": "R2", "rule_id": "env.co2.high",
       "statement": "최근 24시간 중 침실 CO2가 1,000ppm 초과 6시간",
       "source": "실내공기질 관리법 유지기준 준용", "severity": "advisory"}
    ],
    "excluded": "원시 측정값·측정 시각·기기 식별자·정확 연령·실명은 포함하지 않음"
  },
  "answer_constraints": {
    "must_cite_every_medical_claim": true,
    "must_not_diagnose": true,
    "must_not_prescribe": true,
    "must_not_interpret_personal_data_beyond_findings": true,
    "personal_reference_format": "[R#]"
  }
}
```

- **밴딩 규칙**: 정확 수치 대신 임상 분류 밴드, 정확 나이 대신 10세 밴드, 약물명 대신 ATC 계열. 시각은 상대 표현.
- 자유 텍스트 질문은 기존 마스킹 경로, 시스템 주입 개인 컨텍스트는 밴딩 경로 — 두 경로 모두 통과 후 프롬프트 조립.
- `llm_providers` 테이블에 `region`, `data_processing_terms` 컬럼 추가로 라우팅 시 강제.

### 5.2 생체신호 해석의 책임 한계 — "해석은 규칙, 서술은 LLM"

3중 방어:
1. **입력 측**: LLM이 받는 개인 데이터는 findings뿐 — 원시 시계열 미제공으로 자체 분석이 구조적으로 불가능.
2. **프롬프트 제약**: "findings에 없는 개인 수치 해석 생성 금지, 개인 관련 문장은 반드시 [R#] 인용".
3. **출력 검증**: `citation_verifier.py` 확장 — `[R#]` 미인용 개인 수치 문장 제거/재생성. 가드레일에 "수치 진단 표현" 규칙 추가.

레드플래그 EMERGENCY는 LLM을 **거치지 않고** 결정적 템플릿으로 즉시 응답(기존 119/109 경로 사상의 연장).

### 5.3 감사 추적

`rag_queries` 확장:

| 추가 컬럼 | 목적 |
|----------|------|
| `personal_context_hash` | 답변 시점 개인 컨텍스트 SHA-256 — 원문 미저장 재현 |
| `rule_version`, `rule_findings_json` | 규칙 버전·findings 기록(비식별 밴드) |
| `consent_ref` | 당시 유효 동의 원장 ID |
| `jurisdiction`, `feature_flags_snapshot` | 규제 대응 |

개인 데이터 *접근* 감사(`personal_audit_log`)는 별도 테이블(접속기록 보관 기준, GDPR 제30조).

---

## 6. 기술 선택 트레이드오프와 단계별 도입 순서

### 6.1 종합 트레이드오프 표

| 결정 | 선택 | 대안 | 선택 근거 |
|------|------|------|----------|
| 시계열 저장 | Cloud SQL PG 파티셔닝 + 스냅샷 | Timescale, BigQuery, Bigtable | Cloud SQL은 timescaledb 미지원. 조인+운영 단순성 우선. BigQuery는 콜드 계층만 |
| 웹 프레임워크 | FastAPI (신규 → 전체) | Flask, stdlib 유지, Go | Pydantic+OpenAPI+SSE+async 모두 필요 |
| IoT 수집 | 관리형 MQTT → Pub/Sub → Cloud Run push | 자체 브로커, 제조사 API 폴링 | **센서 1~2종 제휴 시 제조사 API 폴링이 최저비용**. GCP IoT Core 단종(2023) 제외 |
| PHR 연동 | 마이헬스웨이 사용자 주도 동기화(FHIR 파싱 라이브러리만) | 자체 FHIR 서버(HAPI), GCP Healthcare API | 풀 FHIR 서버는 팀 규모 초과 |
| 임베딩 | OpenAI 1536 primary 유지, BGE-M3 1024 secondary(예약) | 즉시 전환 | 듀얼 컬럼+상태머신 기존 준비 활용, 다국어 시점에 전환 |
| LLM | `llm_providers` 확장(리전·계약 컬럼) | 단일 고정 | 데이터 처리 위치·zero-retention이 우선 변수 |
| 한국어 검색 | Kiwi(또는 mecab-ko) 형태소 보조 | 그대로, ES+nori | ES는 인프라 +1 — pgvector+tsvector 유지 |
| 평가 | 골든셋 + CI 회귀 평가 | 수동 QA | 개인화는 회귀 면적 배가 — 골든셋 없이 변경 불가 |
| 멀티리전 | 리전별 풀스택 + KB 단방향 복제 | 글로벌 단일 DB, Spanner | 거주성 요건이 글로벌 DB 배제 |

### 6.2 단계별 도입 순서

**Phase 0–3개월 — "개인화 MVP + 안전 토대" (KR 단일 리전)**
1. `consent_ledger` + 동의 UI/게이트 (법적 선행조건)
2. `personal.*` 스키마 — 수집원은 앱 수동 입력 + HealthKit/Health Connect 배치부터
3. `ingest_server.py`(FastAPI) 신규 Cloud Run 서비스
4. `medical_shared.vital_rules` 레드플래그 엔진 v1 (~15규칙, 전 규칙 출처 명기, 단위테스트 100%)
5. Evidence Pack `personal_context` 주입 + `[R#]` 검증 — KR 플래그만 ON
6. **골든 평가셋 v1**(비개인화 200 + 개인화 50문항) — CI 배선
7. 감사 확장 컬럼

**Phase 3–6개월 — "PHR 연동 + 서버 전환"**
1. 마이헬스웨이 연동(사용자 주도, FHIR JSONB 보존 + KCD/ATC/KD 파생)
2. **투약 이력 × DUR 교차조회**(정보 표시 한정): 최대 차별화 기능
3. RAG 서비스 FastAPI 전환 완료, `rag_server.py` 폐기
4. IoT 정식 경로(센서 전략 확정 후), 다운샘플링·보존 정책
5. 피드백 수집 배선 + 개인화 답변 표본 검수
6. 멀티턴 문맥화 + Kiwi 형태소 보강
7. 식약처 웰니스 적합성 문서화(Intended Use Statement 확정) — 외부 자문 1회

**Phase 6–12개월 — "글로벌 + 고도화"**
1. 두 번째 리전(EU 또는 US) 풀스택 복제, EU는 DPIA + 레드플래그 보수화/비활성
2. BGE-M3 dual_indexing → shadow_eval → 다국어 검색 전환
3. 학습형 리랭커(골든셋 향상 입증 시에만)
4. BigQuery 콜드 계층
5. SaMD 전환 타당성 평가 — 결정적 규칙 엔진·감사·골든셋이 인허가 기술문서 자산

---

## 맺음말 — 경쟁 우위의 본질

GPT/Gemini가 따라올 수 없는 것은 모델이 아니라 **(1) 사용자의 동의 기반 종단 건강 컨텍스트, (2) KDCA·DUR·심평원 등 한국 공공 근거의 구조화된 우선순위 검색, (3) 모든 문장이 `[E#]`/`[R#]`로 감사 가능한 책임 구조**다. 본 설계는 이 세 가지를 기존 코드베이스의 검증된 골격 위에 추가적(additive)으로 쌓으며, 의료기기 경계는 문구 검토가 아닌 아키텍처(규칙 엔진 + 관할 플래그 + 출력 검증)로 강제한다. 1~3인 팀이 12개월 내에 도달 가능한 범위로 운영 대상 증가를 최소화했다.
