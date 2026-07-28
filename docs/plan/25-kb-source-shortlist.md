# KB 출처 정제 숏리스트 — 30개 후보 → canonical 채택

> 작성: 2026-06-24 (구 22 — production-app-plan과 번호 충돌로 25 리네임) · 입력 = 외부 세션이 제시한 분야별 출처 후보 30개(SW1–SW30)
> 정제 규칙 = [[kb-ingest-hardening]] 메모리 / 라이선스 원칙 = [04-kb-expansion-list.md](04-kb-expansion-list.md) P4(본문 적재는 PD/KOGL-1/CC BY만, NC·ND는 메타데이터+딥링크만)
> 구현 현황(2026-06-25): **정규화·dedup = `kb_url_normalize.py`**(ingest 멱등성 배선) · **언어/저밀도 필터 = `kb_content_filter.py`**(collect 품질게이트 배선) · **상세 URL 전개기 = `kb_link_expander.py`** 구현 완료. 남은 것 = 아래 "갭 & 다음 액션".

## 결과 요약

| 단계 | 수 |
|---|---|
| raw 후보 | 30 |
| 정규화(jsessionid·ACSTracking·deliveryName·s_cid 제거)+dedup 후 **distinct canonical** | **14** |
| 필터(언어·저밀도·한국제도 충돌) 통과 = **채택** | **5** |
| └ 즉시 적재 가능 | 2 (PHWR 한국 주출처 1 + CDC 심혈관 보조 1) |
| └ 한국 주출처 **seed**(진입 URL → 상세 전개 필요) | 3 |
| 제외 | 9 |

> ⚠️ 메모리에 기록됐던 "실효 고유 11 / 한국 공식 34"는 **이 30개 목록 기준이 아님** — 실제 도출은 distinct 14, 한국 공식 canonical 4개(채택). 34는 다른/더 큰 인벤토리 수치로 추정.

## ✅ 채택 (canonical 5)

| # | 분야 | canonical URL | 출처 / tier | 라이선스 | 적재 상태 | 근거 |
|---|---|---|---|---|---|---|
| K1 | 감염병 통계·감시 | `https://www.phwr.org/journal/view.html?pn=vol&uid=786&vmd=Full` | PHWR 주간건강과질병 / **한국 주** | 공공누리(유형 확인 필요) | **즉시 적재** | 법정감염병 연보 실콘텐츠. SW20/22/23/24 중복 → 1 |
| K2 | 만성질환·심혈관 | `https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5311a5.htm` | CDC MMWR / 보조 | US PD(본문 가능) | **즉시 적재(보조)** | 충돌영역 아님. 단 KDCA(K3)가 주출처면 보조/딥링크로 충분 |
| K3 | 만성질환·심혈관 | `https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/cbvcacdAfterMain.do` | KDCA 심뇌혈관 포털 / **한국 주** | 공공누리(유형 확인 필요) | **seed — 상세 전개** | `...AfterMain.do`=진입 페이지. 뇌졸중·심근경색·CPR 등 상세 URL 펼쳐 수집. SW8–12 중복 → 1 |
| K4 | 정신건강 | `https://www.mentalhealth.go.kr/portal/main/index.do` | 국가정신건강정보포털 / **한국 주** | 공공누리(유형 확인 필요) | **seed — 상세 전개** | `index.do`=포털 메인. 질환정보·자가검진 상세 페이지로 전개. SW15/16 중복 → 1 |
| K5 | 환경·유해요인 | `https://health.kdca.go.kr/healthhazard/intrcnInfo/hrIntrcnMain` | KDCA 건강위해정보 / **한국 주** | 공공누리(유형 확인 필요) | **seed — 상세 전개** | `hrIntrcnMain`=진입 페이지. 위해요인 주제별 상세로 전개. SW25–30 중복 → 1 |

## ❌ 제외 (9) — 사유

| canonical | 분야 | 제외 사유 |
|---|---|---|
| `medlineplus.gov/spanish/ency/article/002024.htm` (SW2) | 예방접종 | **스페인어**(`/spanish/`) |
| `cdc.gov/other-spotted-fever/es/.../epidemiologia-y-estadisticas.html` (SW21) | 감염병 | **스페인어**(`/es/`) + 법정감염병 충돌 |
| `medlineplus.gov/vaccines.html` (SW1) | 예방접종 | 예방접종=**한국제도 충돌→한국 출처 전용** + overview 허브(저밀도) + 보조 |
| `cdc.gov/vaccines/hcp/administration/resources.html` (SW3) | 예방접종 | 링크모음(저밀도) + 예방접종 충돌 |
| `cdc.gov/vaccines/php/imz-program-resources/partner-websites.html` (SW4) | 예방접종 | 순수 파트너 **링크모음** + 예방접종 충돌 |
| `cdc.gov/mmwr/preview/mmwrhtml/rr5515a1.htm` (SW5=SW6 대소문자 dup) | 예방접종 | ACIP 일반 권고(실콘텐츠지만) **예방접종 스케줄=한국제도 충돌→한국 전용** |
| `medlineplus.gov/mentalhealth.html` (SW13/14/17) | 정신건강 | overview 허브(저밀도) + 한국 주출처(K4) 존재로 보조 불필요 |
| `mentalhealth.go.kr/portal/health/fac/PotalHealthFacListTab2.do?...` (SW18) | 정신건강 | **기관 목록/검색 페이지**(콘텐츠 아님·저밀도) |
| `cdc.gov/mmwr/volumes/72/wr/mm7219e1.htm` (SW19) | 감염병 | COVID 감시 = **법정감염병 통계 충돌→한국 출처 전용** |

## 적용한 정규화 규칙

- **제거 파라미터**: `jsessionid`(KDCA 5+6건), `ACSTrackingID`·`ACSTrackingLabel`·`deliveryName`(SW19), `s_cid`(SW19). 대소문자 경로 정규화(`mmwR`→`mmwr`, SW5=SW6).
- **유지 파라미터**(콘텐츠 식별자): PHWR `pn`·`uid`·`vmd`.
- **언어 차단**: `/spanish/`, `/es/`.
- **저밀도 스킵**: 포털 메인(`index.do`)·링크모음(`resources`/`partner-websites`)·시설 목록(`...FacListTab2.do`)·주제 overview 허브(`vaccines.html`/`mentalhealth.html`). 단 한국 주출처의 진입 페이지(K3/K4/K5)는 제외가 아니라 **seed로 보존 후 상세 전개**.
- **한국제도 충돌 영역(예방접종 스케줄·법정감염병) = 한국 출처 전용**: 해당 영역 CDC/MedlinePlus 전부 제외.

## 갭 & 다음 액션 (RAG 세션)

1. **예방접종 = 채택 0** — 이 배치에 한국 예방접종 출처가 없음. KDCA 예방접종도우미(`nip.kdca.go.kr`)를 별도 확보해야 함. (이미 `seed_vaccination_kb.py` NIP 5문서 존재 — 중복/보강 여부 점검)
2. ~~seed 3개(K3/K4/K5) 상세 URL 전개기 필요~~ → ✅ **구현+배선 완료(2026-06-25)**: `kb_link_expander.expand_detail_urls` + **`collect_public_kb.fetch_shortlist`**(`--source shortlist`, opt-in — 'all' 미포함). 설정 = `kb_shortlist_sources.py`(K1~K5 + include_re 섹션 제한 + 신규 출처 등록행). 테스트 `tests/test_kb_shortlist.py`.
3. **라이선스 유형 확정(사람 확인 필요 — 유일한 남은 차단)** — **K1 PHWR·K4 정신건강포털 = `kogl_pending`으로 fail-closed 보류 중**(수집기가 fetch 자체를 스킵+경고). 출처 사이트에서 공공누리 유형 확인 후 `kb_shortlist_sources.py`의 `license`를 `kogl_type1`로 갱신하면 자동 수집. K3/K5는 기존 health_kdca 등록(kogl_type1) 재사용, K2는 US public domain(`evidence_country=US`·`regulatory_korea=False`로 적재).
4. ~~collect_public_kb.py에 정규화 전처리 추가~~ → ✅ 구현 완료: `kb_url_normalize`(ingest 멱등성 배선) + `kb_content_filter`(수집 품질게이트 배선).
5. **라이브 1차 실행** — `python collect_public_kb.py --source shortlist --dry-run`으로 전개 결과 미리보기 후 적재. KDCA 포털 실HTML에서 전개 0건이면 include_re 패턴을 실측 조정.

## 부록 — 기계 판독용 (collect 입력 후보)

```json
[
  {"id":"K1","domain":"infectious_surveillance","url":"https://www.phwr.org/journal/view.html?pn=vol&uid=786&vmd=Full","source":"phwr","tier":"primary_kr","license":"kogl_verify","status":"ingestible"},
  {"id":"K2","domain":"cardiovascular","url":"https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5311a5.htm","source":"cdc_mmwr","tier":"secondary","license":"us_public_domain","status":"ingestible_optional"},
  {"id":"K3","domain":"cardiovascular","url":"https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/cbvcacdAfterMain.do","source":"health_kdca","tier":"primary_kr","license":"kogl_verify","status":"seed_expand"},
  {"id":"K4","domain":"mental_health","url":"https://www.mentalhealth.go.kr/portal/main/index.do","source":"mentalhealth_go_kr","tier":"primary_kr","license":"kogl_verify","status":"seed_expand"},
  {"id":"K5","domain":"environmental_hazard","url":"https://health.kdca.go.kr/healthhazard/intrcnInfo/hrIntrcnMain","source":"health_kdca","tier":"primary_kr","license":"kogl_verify","status":"seed_expand"}
]
```
