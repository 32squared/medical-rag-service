# 30. 공신력 있는 국내 기관 RAG 데이터 후보·접근 방법·자동 구축 계획 (2026-10-28)

> 전제: 신뢰 모드(`RAG_TRUSTED_SOURCES_ONLY`, PR #19)로 기관 원문·공식 기록만 검색한다. 이 문서는 그 모드에서 **쓸 수 있는 국내 출처를 넓히는** 계획이다.
> 조사 근거: 2026-10-28 WebSearch·WebFetch 로 직접 확인한 것만 적었다(확인 못 한 항목은 §7). 선행: docs/plan/29(현황·과제), 25(숏리스트), 24(출처 조사).
> 코드: `kb_catalog.py`(출처 카탈로그) · `kb_collect/`(수집 프레임워크) · `collect_kb.py`(CLI·잡 진입점) · `migrations/026_kb_collect_runs*.sql`(실행 기록).

## 0. 결론 (한 장)

| 구분 | 결론 |
|---|---|
| 지금 당장 원문 적재 가능한 공인 출처 | **식약처 공공데이터포털 OpenAPI 5종**(e약은요·DUR·안전성서한·제품허가·영양성분, 이용허락 "제한 없음") + **법제처 고시·행정규칙 원문**(저작권 비보호). 둘 다 **인증키만 있으면 자동 수집**된다 |
| 협의 없이는 못 쓰는 것 | 국가건강정보포털(공공누리 **제4유형** = 상업 이용·변경 금지), 응급의료포털·국가암정보센터·예방접종도우미(영리 사전협의), 질병청 보도자료(개별 공공누리 마크 없음), 학회·병원 전부(All rights reserved) |
| 수집 불가 | 건강iN(robots 전면 차단·API 없음), 의약품안전나라 HTML(robots), 한국의약품안전관리원(robots) |
| 자동화 시스템 | 카탈로그 1건 = 출처 1개. `collect_kb.py --status` 가 출처마다 "사람이 해 줄 일"(키·라이선스) 을 보여 주고, `--due` 가 주기 지난 활성 출처만 수집·적재·기록한다. Cloud Run 잡 + Cloud Scheduler 로 돌린다(§4) |
| 사용자에게 필요한 것 | §6 — data.go.kr 활용신청 4건, law.go.kr 키 1건, 질병청·국립암센터 협의 여부 결정, Cloud Scheduler API 활성화 |

## 1. 후보 목록 — 공공기관 OpenAPI (공공데이터포털 data.go.kr)

이용허락 "제한 없음" = 포털 표기. 승인 "자동/심의" = 개발계정/운영계정. 트래픽은 개발계정 기준(운영은 활용사례 등록 뒤 증량 신청).

| 우선 | 기관 | 서비스명 | 포털 번호 | 콘텐츠 | 이용허락 | 승인 | 카탈로그 id |
|---|---|---|---|---|---|---|---|
| **1** | 식약처 | 의약품개요정보(e약은요) | 15075057 | **일반인 설명문**(효능·사용법·주의·상호작용·부작용·보관, 일반의약품) | 제한 없음 | 자동/심의, 10,000/일 | `mfds_drug_info` (엔드포인트·필드 매핑 완료) |
| 1 | 식약처 | DUR 품목정보 | 15059486 | 기준·코드(병용·연령·임부금기 등 8종) | 제한 없음 | 자동/자동 | `mfds_dur` (이미 112건, 재수집 가능) |
| **2** | 식약처 | 의약품안전성서한 정보 | 15059182 | 설명문(제목·요약·상세·조치) | 제한 없음 | 자동/자동 | `mfds` (HTML → OpenAPI 전환) |
| 2 | 식약처 | 의약품 제품 허가정보 | 15095677 | 품목·주성분·허가(효능효과 텍스트 포함 여부 미확인) | 제한 없음 | 자동/심의 | `mfds_drug_permit` |
| 3 | 식약처 | 식품영양성분DB | 15127578 | 수치(영양성분) | 제한 없음 | 자동/심의 | `mfds_food_nutrition` (조회형 권장) |
| 3 | 식약처(식품안전나라) | 건강기능식품 품목제조신고(I0030)·품목분류(I2710) | foodsafetykorea.go.kr | **설명문**(주된기능성·섭취시주의사항·섭취방법) | 식약처 저작권정책(자유이용, 유형 미명시) | 별도 회원가입·키 | `mfds_hff` |
| 4 | 질병청 | 전수신고 감염병 발생현황 | 15139178 | 통계 | 공공누리 1유형 | 자동/자동, 1,000/일 | `kdca_api` |
| — | 질병청 | 국가건강정보포털 | 15087442 (LINK) | 설명문 | **공공누리 4유형** | 자동/심의 | `health_kdca` (협의 전 보류) |
| — | 질병청 | 예방접종 정보 | 15084296 | 감염병 코드만 | 제한 없음 | 자동/자동 | (내용 없음, 제외) |
| — | 건보공단 | 검진기관 찾기 등 3종 | 15154419… | 기관 코드 | 1유형 | 자동/자동 | (건강정보 콘텐츠 API **없음**) |
| — | 심평원 | 병원·약국·의약품성분·약가·질병통계 | 15001698 등 | 코드·통계 | 1유형 | 자동 | (답변 근거 아님, 제외) |
| — | 국립중앙의료원 | 전국 응급의료기관 정보 | 15000563 | 기관·병상 | 제한 없음 | 자동/자동 | (응급 안내 툴로는 유용, KB 아님) |

## 2. 후보 목록 — 사이트 직접 수집(HTML) · 법령

| 우선 | 출처 | 저작권·이용 조건(확인 URL) | robots | 판정 | 카탈로그 id |
|---|---|---|---|---|---|
| **1** | 국가법령정보센터 OPEN API(DRF) — 복지부 고시·행정규칙 | 저작권법 제7조 비보호, 출처(법제처) 표기 의무. open.law.go.kr 회원가입 → 활용신청 → **담당자 승인 1~2일** | Allow: / | **원문 적재(official_record)**. 본문 API 가 별표 내용·별표 파일링크를 준다 → 건강검진·예방접종 실시기준 별표를 요약(checkup_std_kr) 대신 원문으로 | `law_kr_notice` |
| 2 | 국가건강정보포털 health.kdca.go.kr | **공공누리 제4유형**(출처표시·비상업·변경금지), FAQ "영리 목적 사용 불가, 내용 편집 불가" (cpyrhtPolicy.do, 2023-02-27) | 없음(404) | **질병관리청 협의 필요**. 대한의학회 감수 835종·답변 93% 의존 → 협의 1순위 | `health_kdca` |
| 3 | 질병청 보도자료 kdca.go.kr | 저작권정책: 제1유형 **표시된** 자료만 자유이용, 게시글엔 개별 마크 없음 | /search.do 만 차단 | 협의 필요(마크 확인 요청) | `kdca_press` |
| 3 | 국가암정보센터 cancer.go.kr | 공공누리 아님. 비영리만·출처표시·변경금지, 정보사용신청서 → 내부심사, 딥링크 불허 | 콘텐츠 경로 허용 | 국립암센터 정보사용신청 필요 | `cancer_go_kr` |
| 3 | 응급의료포털 e-gen.or.kr | 영리 이용 사전협의·출처표시, 응급처치 이미지 외부 사용 불가 (guide/copyright.do) | 제한 없음 | 협의 필요(기적재분 유지) | `nemc` |
| 4 | 예방접종도우미 nip.kdca.go.kr | All rights Reserved, 공공누리 없음, 저작권정책 페이지 없음 | 없음 | 협의 필요. 표준 일정은 고시 별표(law_kr_notice)로 먼저 | `kdca_nip` |
| 4 | 감염병포털 dportal.kdca.go.kr · 국가정신건강정보포털 | 공공누리 로고만, 유형 미표시 → "협의" | Allow 일부 | 숏리스트(kb_shortlist_sources) fail-closed 유지 | `shortlist` |
| ✕ | 건강iN hi.nhis.or.kr / nhis.or.kr | 건강정보 페이지 공공누리 미부착. **robots /nhis/ 전체 Disallow**, hi.nhis.or.kr TLS 불일치, API 없음 | 차단 | 수집 불가 | `nhis_health_in` (blocked) |
| ✕ | 의약품안전나라 nedrug.mfds.go.kr | — | **Disallow: /** | OpenAPI(안전성서한)로 대체 | `mfds` |
| ✕ | 한국의약품안전관리원 drugsafe.or.kr | 상업 이용 금지 | **Disallow: /** | 제외 | — |
| ✕ | 한국건강증진개발원 khepi.or.kr | CC BY-NC(+ND/SA), 영리 사전협의 | 허용 | 비상업 조건 → 제외 | — |
| ✕ | 중앙치매센터 nid.or.kr | All rights reserved, 공공누리 없음 | 없음 | 협의 전 제외 | — |

## 3. 후보 목록 — 학회·상급종합병원·협회 (모두 "허락 필요")

민간 자료는 개방 라이선스가 **한 곳도 없다**. 원문 적재는 각 기관 허락이 필요하고, 그 전까지는 **메타+딥링크**(제목·한 줄 요약·URL 만 두고 답변에서 링크 제시) 로만 쓸 수 있다. 메타+딥링크는 신뢰 모드의 "본문 근거"가 아니므로 별도 설계(§5 Phase 4).

| 기관 | 자료 | 형식·규모 | 저작권 | 창구 | 비고 |
|---|---|---|---|---|---|
| 대한의학회 | 임상진료지침 정보센터 등록 DB(≈110건), 만성질환 일차의료용 권고요약본 10종 | PDF | All rights reserved; **권고요약본 일부는 공공누리(비상업) 표기** — 유형 개별 확인 필요 | kams@kams.or.kr | 일반인 질환정보는 자체 사이트가 아니라 **국가건강정보포털 집필·감수** 형태 → health_kdca 협의가 곧 학회 감수 정보 확보 |
| 대한당뇨병학회 | 일반인 페이지·2025 진료지침 | HTML·첨부 | All rights reserved | diabetes@kams.or.kr | |
| 대한고혈압학회 | 고혈압 수칙·자가관리 | **이미지(텍스트 없음)** | All rights reserved | ksh@koreanhypertension.org | 텍스트 추출 불가 |
| 한국지질·동맥경화학회 | 이상지질혈증 일반인·진료지침 2026 | HTML·첨부(일부 유료) | All rights reserved | ksla@lipid.or.kr | |
| 대한비만학회 | 비만 바로알기·진료지침 요약·팩트시트 | HTML·PDF | 미확인(봇 403) | info@kosso.or.kr | |
| 대한신장학회 | 신장질환 정보·진료지침 20여 건 | HTML·**PDF 직접 링크** | All rights reserved | ksn@ksn.or.kr | 학회 중 PDF 접근성 최고 |
| 대한간학회 | 간질환 바로알기 9종·소책자·가이드라인 | HTML·첨부 | 저작권 문구 미확인 | 미확인 | |
| 대한소아청소년과학회 | 질환상식·육아정보 | 게시판 | All rights reserved | pediatrics@pediatrics.or.kr | 예방접종지침서는 유료 간행물 |
| 대한신경과학회 | 증상·질병 10종·안내서 PDF | HTML·PDF | All rights reserved | kna@neuro.or.kr | |
| 대한내과학회 | 진료지침 자료실(PDF 다수) | PDF | All rights reserved | kaim4364@kaim.or.kr | 일반인 메뉴 없음 |
| 대한심장학회·신경정신의학회·가정의학회·의사협회 | 일반인 자료 미확인/없음 | — | — | — | 제외 |
| 서울대병원 | N의학정보 **1,874건** | HTML(정의·원인·증상·진단·치료·예방·식이) | 약관 13조 사전승낙 없는 영리 이용 금지 | 창구 미명시 | robots 허용 |
| 서울아산병원 | 질환백과 **1,286건**+증상백과 | HTML | 의료정보운영방침: 사전 승낙·협의, **콘텐츠제공 신청 절차 있음**(무상·비상업·비재가공) | mcc@amc.seoul.kr | 4개 병원 중 유일하게 공식 신청 절차. "재가공 불가"라 RAG 요약 생성이 저촉될 수 있어 협의 필요 |
| 삼성서울병원 | 질환백과 | HTML(규모 미확인) | 약관 22조 사전승낙 | 미명시 | |
| 세브란스 | 질환백과(health.severance.healthcare) | HTML | 약관 18조 사전승낙 | 미명시 | |
| 대한약사회 | 의약품 복용법 14항목 | HTML | All rights reserved | 02-581-1201 | 소규모, 식약처 e약은요가 대체 |
| 약학정보원 | 의약품 검색 4만종 | DB | 회원 전용·재이용 조건 미확인 | 1670-5877 | e약은요 우선 |

## 4. 자동 구축 시스템 (이번 PR 에 구현)

```
kb_catalog.CATALOG ──(status·license·key_env·api)──▶ collect_kb.py --status   # 사람이 해 줄 일 표
        │
        ▼  effective_status == active 이고 (--due 면) cadence 경과
kb_collect.runner.run_sources
   ├─ fetchers.get(entry.fetcher)(entry, max_items, env, clients)   # OpenAPI(datagokr_generic) / HTML / 법령 DRF
   ├─ kb_content_filter.assess_content      # 길이·링크팜·저가치 URL
   ├─ collect_public_kb.precheck_violations # 가드레일 사전검사(진단·처방·면책)
   ├─ label_evidence_topic                  # 한국어 주제 라벨(게이트 정렬)
   ├─ kb_ingest.ingest_document(upsert=False, match_url)   # 체크섬 바뀐 문서만 갱신, 그 외 skipped
   └─ ledger.record_run → kb_collect_runs   # fetched/inserted/updated/skipped_*/errors, 상태 ok|empty|fetch_error|not_implemented
```

| 구성 | 역할 | 사람이 바꾸는 것 |
|---|---|---|
| `kb_catalog.py` | 출처 1건 = dict 1개. `status`(active/pending_key/pending_license/pending_verify/blocked), `license`(유형·확인일·확인 URL·메모), `provenance`(source_trust 와 테스트로 일치 강제), `api`(엔드포인트·필드 매핑), `content_kind`(prose/codes/stats) | 키 받으면 `status: active`, 협의 끝나면 `license.type` 갱신. 코드 변경은 그것뿐 |
| `kb_collect/clients.py` | data.go.kr 클라이언트(페이징·resultCode 검사·XML 폴백·요청 간격), robots 를 보는 HTML 클라이언트, 파일 다운로드 | — |
| `kb_collect/parsers.py` | 레코드 → 문서(제목·섹션별 본문·출처 URL·체크섬·게시일) | — |
| `kb_collect/fetchers.py` | 수집기 레지스트리. 기존 수집기(health_kdca·nemc·DUR·숏리스트) 래핑 + `datagokr_generic`(카탈로그 api 설정만으로 동작) + 미구현 스텁(`not_implemented` 로 드러남) | 새 OpenAPI 출처는 코드 없이 카탈로그 `api` 만 |
| `kb_collect/ledger.py` | `kb_collect_runs` 기록·`last_success`·`is_due` | — |
| `collect_kb.py` | `--status` / `--source a,b` / `--all` / `--due` / `--dry-run` / `--max` / `--runs`. 실패 출처가 있으면 exit 1 | — |
| 게이트(fail-closed) | 라이선스가 `INGEST_LICENSES`(public_domain·kogl_type0·kogl_type1·datagokr_unrestricted·cc_by) 밖이면 active 라도 수집하지 않음. 키 없으면 pending_key. robots 가 막으면 HTML 클라이언트가 거부 | 허용 목록 변경은 법무 결정 뒤 |

운영 배선(다음 PR, 사람 확인 필요):
1. Cloud Run 잡 `kb-collect`(이미지 = 서비스 이미지, 명령 `python collect_kb.py --due`, env: DATABASE_URL·DATA_GO_KR_KEY·LAW_GO_KR_KEY 는 Secret Manager). 기존 `collect-public-kb` 잡은 5월 이미지라 교체.
2. Cloud Scheduler(주 1회, 월 03:00 KST) → 잡 실행. **Cloud Scheduler API 가 프로젝트에 아직 활성화되지 않았다**(활성화는 사용자).
3. 실행 뒤 `collect_kb.py --runs` 로 기록 확인, `kb_stats.py` 로 문서 수 확인. 실패(`fetch_error`·`not_implemented`)는 exit 1 → 잡 실패 알림.
4. 새 출처가 처음 적재되면 신뢰 모드 검색에 바로 포함된다(source_trust 등록부에 있으므로). 운영 반영은 dev 실측 뒤 사람 확인.

## 5. 단계별 계획

| 단계 | 내용 | 선행 조건 | 기간(실작업) |
|---|---|---|---|
| **0. 프레임워크** (이번 PR) | 카탈로그·수집기·레저·CLI·테스트 37건 | — | 완료 |
| **1. 키 확보** | data.go.kr 에서 e약은요·안전성서한·제품허가·영양성분 **활용신청**(같은 계정, 서비스별), open.law.go.kr 활용신청(승인 1~2일), 식품안전나라 키 | 사용자 | 신청 30분 + 승인 대기 |
| **2. 약물·고시 원문 적재** | e약은요 적재(dev → 실측 → prod), 안전성서한·제품허가 필드 매핑 채우기(키 발급 뒤 상세기능 탭), 법령 DRF 수집기 구현(행정규칙 본문 + 별표 → official_record), checkup_std_kr 요약을 원문으로 교체 | 1 | 3~5일 |
| **3. 운영 배선** | Cloud Run 잡 + Scheduler, 실패 알림, 주간 `--due` | Scheduler API 활성화(사용자) | 1일 |
| **4. 협의 출처** | 질병관리청(국가건강정보포털 제4유형 상업 이용 협의 — 학회 감수 정보의 사실상 유일한 길), 국립암센터 정보사용신청, 응급의료포털 영리 협의, 질병청 보도자료 공공누리 마크 확인 요청 | 사용자·법무 | 협의 기간 미상(수주) |
| **5. 학회·병원 메타+딥링크** | 본문 없이 제목·요약·URL 만 가진 "안내 링크" 계층을 답변 끝에 붙이는 설계(신뢰 모드 본문 근거와 분리). 서울아산병원 콘텐츠제공 신청은 "재가공 불가" 조건 협의 뒤 | 4 와 병행 | 설계 2일 + 협의 |

커버리지 관점: 현재 답변의 93% 가 health_kdca 에 의존한다(doc 29 §5). 단계 2 로 약물·검진·예방접종 질문은 공인 원문으로 대체되지만, **일반 질환 설명(정의·증상·관리) 은 health_kdca 협의 없이는 공인 대체 출처가 없다** — 법제처 고시·식약처 API 는 그 영역을 덮지 않는다.

## 6. 사용자에게 필요한 것

1. **공공데이터포털 활용신청**(data.go.kr, 기존 DATA_GO_KR_KEY 계정으로): 15075057(e약은요) · 15059182(안전성서한) · 15095677(제품허가) · 15127578(영양성분). 개발계정 자동승인. 승인 뒤 "상세기능" 탭의 요청 URL·필드명을 알려 주면 카탈로그 `api` 를 채운다.
2. **국가법령정보센터 OPEN API 신청**(open.law.go.kr 회원가입 → 활용신청, 1~2일 승인) → 인증값(OC)을 Secret `law-go-kr-key` 로. 사용처: 보건복지부 고시 원문·별표.
3. **식품안전나라 OpenAPI 키**(건강기능식품 설명문) — 필요하면.
4. **협의 여부 결정**: ① 질병관리청 국가건강정보포털 제4유형 상업 이용 협의를 시작할지(가장 큰 레버) ② 국립암센터 정보사용신청 ③ 응급의료포털 영리 협의. 협의 창구는 사용자 측에서 열어야 한다.
5. **Cloud Scheduler API 활성화**(프로젝트 medical-compliance-tester) — 주간 자동 수집용.
6. 우선 도메인: 약물(e약은요) → 검진·예방접종 고시 → 영양제(건기식) 순으로 잡았다. 다른 순서를 원하면 조정.

## 7. 확인 못 한 것

- data.go.kr 상세페이지가 JS 렌더라 e약은요 외 서비스의 요청 URL·오퍼레이션·필드명은 키 발급 뒤에야 보인다(카탈로그 `api.url: None` 으로 표시, 수집기는 `not_implemented` 로 드러냄).
- 제품허가정보 API 에 효능효과·용법용량 텍스트가 있는지. 국가건강정보포털 LINK API 의 실제 호출 주소.
- 법제처 OC 형식(이메일 ID 여부)·IP 등록·호출 한도, 별표 파일링크 다운로드 동작.
- 식품안전나라 저작권정책 본문, 건기식 API 호출 한도 단위.
- 대한의학회 권고요약본 PDF 의 공공누리 유형(일부 비상업 표기), guideline.or.kr 로그인 요구 여부.
- 서울대·삼성·세브란스 콘텐츠 이용 허락 창구.
