"""
kb_catalog.py — 공인 기관 KB 출처 카탈로그 (자동 구축 시스템의 단일 설정).

수집기(kb_collect.runner)는 이 카탈로그만 보고 돈다. 출처 하나 = 항목 하나:
  id            kb_sources.id / source_trust 등록 id
  institution   기관 공식 명칭(표시용)
  access        접근 방식: openapi_datagokr | openapi_foodsafetykorea | html | file | law_drf
  fetcher       kb_collect.fetchers 의 함수 이름 (카탈로그 항목과 max_items 를 받아 문서 dict 목록 반환)
  key_env       필요한 인증키 환경변수(없으면 None)
  license       등록 라이선스 값 + 확인 정보 {type, verified_at, verify_url, note}
  provenance    source_trust 의 출처 성격(기관 원문 = institution_verbatim …)
  cadence_days  갱신 주기(일) — ledger 의 마지막 성공 뒤 이 일수가 지나면 due
  status        사람이 정하는 상태:
                  active          — 자동 수집 대상
                  pending_key     — 인증키 발급·활용신청 대기
                  pending_license — 라이선스·법무 결정 대기(수집하지 않음)
                  pending_verify  — 접근 방법·라이선스 미확인(후보)
                  blocked         — robots/약관으로 수집 불가
  match_url     ingest 멱등 판정에 URL 도 쓸지(큐레이션처럼 대표 URL 을 공유하면 False)
  routes        retrieval_router 라우트 라벨(참고)
  api           (openapi 항목) datagokr_generic 수집기 설정 {url, params, items_path, title_field, body_fields, …}
  content_kind  설명문(prose) | 기준·코드(codes) | 통계(stats) — RAG 근거로 쓸 수 있는 건 prose

실제로 돌릴 수 있는지는 effective_status() 가 환경(키 존재)·라이선스 허용 목록과 함께 판정한다.
라이선스 유형 값:
  public_domain          법령·고시(저작권법 제7조 비보호)
  kogl_type0 / kogl_type1 공공누리 제0·제1유형(출처표시만)
  datagokr_unrestricted  공공데이터포털 "이용허락범위: 제한 없음"
  cc_by
  kogl_type2~4 / cc_by_nc / terms_restricted / unknown  → 본문 적재 불가(fail-closed)

조사 근거: docs/plan/30-kb-auto-build-plan-20261028.md (2026-10-28 WebFetch 확인분).
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

ACCESS_OPENAPI = "openapi_datagokr"
ACCESS_OPENAPI_FOODSAFETY = "openapi_foodsafetykorea"
ACCESS_HTML = "html"
ACCESS_FILE = "file"
ACCESS_LAW_DRF = "law_drf"
ACCESS_VALUES = (ACCESS_OPENAPI, ACCESS_OPENAPI_FOODSAFETY, ACCESS_HTML, ACCESS_FILE, ACCESS_LAW_DRF)
KEYED_ACCESS = (ACCESS_OPENAPI, ACCESS_OPENAPI_FOODSAFETY, ACCESS_LAW_DRF)

STATUS_ACTIVE = "active"
STATUS_PENDING_KEY = "pending_key"
STATUS_PENDING_LICENSE = "pending_license"
STATUS_PENDING_VERIFY = "pending_verify"
STATUS_BLOCKED = "blocked"
HUMAN_STATUSES = (STATUS_ACTIVE, STATUS_PENDING_KEY, STATUS_PENDING_LICENSE,
                  STATUS_PENDING_VERIFY, STATUS_BLOCKED)

# 본문 적재가 허용되는 라이선스(docs/plan/04 P4 + 공공누리 제0유형 + 공공데이터포털 '제한 없음')
INGEST_LICENSES = frozenset({"public_domain", "kogl_type0", "kogl_type1", "datagokr_unrestricted", "cc_by"})

DATA_GO_KR_KEY = "DATA_GO_KR_KEY"            # 공공데이터포털 일반 인증키(서비스별 활용신청)
LAW_GO_KR_KEY = "LAW_GO_KR_KEY"              # 국가법령정보센터 OPEN API 인증값(OC)
FOODSAFETY_KR_KEY = "FOODSAFETY_KR_KEY"      # 식품안전나라 OpenAPI 인증키

_DATAGOKR = "https://www.data.go.kr/data/{}/openapi.do"


def _lic(type_: str, verified_at: Optional[str] = None, verify_url: str = "", note: str = "") -> Dict:
    return {"type": type_, "verified_at": verified_at, "verify_url": verify_url, "note": note}


_DRUG_DISCLAIMER = "본 정보는 식품의약품안전처 공개 자료를 그대로 옮긴 것으로, 실제 복용은 의사·약사와 상담하십시오."

CATALOG: List[Dict] = [
    # ── 이미 수집기가 있는 출처 ──────────────────────────────────
    {
        "id": "health_kdca", "institution": "질병관리청 국가건강정보포털",
        "access": ACCESS_HTML, "fetcher": "health_kdca", "key_env": None,
        "license": _lic("kogl_type4", "2026-10-28",
                        "https://health.kdca.go.kr/healthinfo/biz/health/useGuidance/cpyrhtPolicy.do",
                        "제4유형(출처표시·상업적 이용 금지·변경 금지). FAQ: 영리 목적 사용·내용 편집 불가. "
                        "상업 서비스 본문 적재는 질병관리청 협의 필요"),
        "provenance": "institution_verbatim", "cadence_days": 30, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["KDCA"],
        "note": "대한의학회·서울대 산학협력단 집필·감수, 835종. 답변 93% 가 인용하는 최대 출처. "
                "공공데이터포털 LINK API(15087442)도 같은 제4유형. 결정 전까지 기적재분 유지, 재수집 안 함",
    },
    {
        "id": "nemc", "institution": "중앙응급의료센터 응급의료포털(E-Gen)",
        "access": ACCESS_HTML, "fetcher": "nemc", "key_env": None,
        "license": _lic("terms_restricted", "2026-10-28", "https://www.e-gen.or.kr/guide/copyright.do",
                        "공공누리 아님. 영리 이용 사전 협의·출처 표시, 응급처치 이미지는 외부 사용 불가"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["NEMC"],
    },
    {
        "id": "mfds_dur", "institution": "식품의약품안전처 DUR 품목정보",
        "access": ACCESS_OPENAPI, "fetcher": "mfds_dur", "key_env": DATA_GO_KR_KEY,
        "license": _lic("datagokr_unrestricted", "2026-10-28", _DATAGOKR.format(15059486),
                        "이용허락범위 '제한 없음'. 활용신청 자동승인, 개발계정 10,000건/일"),
        "provenance": "institution_verbatim", "cadence_days": 30, "content_kind": "codes",
        "status": STATUS_ACTIVE, "match_url": True, "routes": ["MFDS_DUR"],
        "note": "DUR 8종(병용금기·연령금기·임부금기 등). 2026-05-29 112문서 적재. 성분 단위 DUR 은 15056780",
    },
    {
        "id": "mfds_drug_info", "institution": "식품의약품안전처 e약은요(의약품개요정보)",
        "access": ACCESS_OPENAPI, "fetcher": "mfds_drug_info", "key_env": DATA_GO_KR_KEY,
        "license": _lic("datagokr_unrestricted", "2026-10-28", _DATAGOKR.format(15075057),
                        "이용허락범위 '제한 없음'. 개발 자동승인·운영 심의, 10,000건/일. 현재 키는 '등록되지 않은 서비스키'"),
        "provenance": "institution_verbatim", "cadence_days": 30, "content_kind": "prose",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["MFDS_DUR"],
        "api": {
            "url": "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
            "params": {}, "items_path": ["body", "items"], "id_field": "itemSeq", "title_field": "itemName",
            "body_fields": [("효능", "efcyQesitm"), ("사용법", "useMethodQesitm"),
                            ("주의사항 경고", "atpnWarnQesitm"), ("주의사항", "atpnQesitm"),
                            ("상호작용", "intrcQesitm"), ("부작용", "seQesitm"), ("보관법", "depositMethodQesitm")],
            "url_template": "https://nedrug.mfds.go.kr/searchDrug/resultDrugDetail?itemSeq={itemSeq}",
            "published_field": "updateDe", "disclaimer": _DRUG_DISCLAIMER, "title_prefix": "",
        },
        "note": "일반의약품 설명문(효능·사용법·주의·상호작용·부작용·보관). 1순위 약물 근거",
    },
    {
        "id": "kdca_api", "institution": "질병관리청 공공데이터 OpenAPI(감염병 발생현황·예방접종 코드)",
        "access": ACCESS_OPENAPI, "fetcher": "kdca_api", "key_env": DATA_GO_KR_KEY,
        "license": _lic("kogl_type1", "2026-10-28", _DATAGOKR.format(15139178),
                        "전수신고 감염병 발생현황: 제1유형, 1,000건/일. 예방접종(15084296)은 감염병 코드만"),
        "provenance": "institution_verbatim", "cadence_days": 30, "content_kind": "stats",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["KDCA", "NIP"],
        "note": "통계·코드라 답변 근거로는 보조. 우선순위 낮음",
    },
    {
        "id": "shortlist", "institution": "숏리스트 K1~K5(PHWR·CDC MMWR·KDCA 심뇌혈관/건강위해·정신건강포털)",
        "access": ACCESS_HTML, "fetcher": "shortlist", "key_env": None,
        "license": _lic("mixed", "2026-09-29", "docs/plan/25-kb-source-shortlist.md",
                        "항목별 라이선스는 kb_shortlist_sources.py 가 fail-closed 로 판정. "
                        "정신건강포털은 공공누리 부착 저작물만 자유이용(미부착 → 협의)"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["KDCA"],
    },
    # ── 새 후보 (2026-10-28 조사 반영) ────────────────────────────
    {
        "id": "law_kr_notice", "institution": "국가법령정보센터 — 보건복지부 고시·행정규칙 원문",
        "access": ACCESS_LAW_DRF, "fetcher": "law_drf_notice", "key_env": LAW_GO_KR_KEY,
        "license": _lic("public_domain", "2026-10-28", "https://open.law.go.kr/LSO/information/guide.do",
                        "법령·고시는 저작권법 제7조 비보호 저작물. 출처(법제처) 표기 의무. "
                        "OPEN API 는 open.law.go.kr 회원가입 → 활용신청 → 담당자 승인(1~2일)"),
        "provenance": "official_record", "cadence_days": 30, "content_kind": "prose",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["KR_GUIDELINE", "LEGAL_POLICY"],
        "api": {
            "search_url": "https://www.law.go.kr/DRF/lawSearch.do",
            "service_url": "https://www.law.go.kr/DRF/lawService.do",
            "target": "admrul", "knd": "3",
            "queries": ["건강검진 실시기준", "예방접종 실시기준", "국가암검진"],
        },
        "note": "건강검진 실시기준 별표·별첨, 예방접종 실시기준 별표 등. 본문 API 가 별표 내용·파일링크를 함께 준다 "
                "→ 기존 checkup_std_kr(요약) 을 원문(official_record)으로 대체",
    },
    {
        "id": "mfds", "institution": "식품의약품안전처 의약품 안전성서한(OpenAPI)",
        "access": ACCESS_OPENAPI, "fetcher": "datagokr_generic", "key_env": DATA_GO_KR_KEY,
        "license": _lic("datagokr_unrestricted", "2026-10-28", _DATAGOKR.format(15059182),
                        "의약품안전성서한 정보: '제한 없음', 자동/자동, 10,000건/일. "
                        "nedrug.mfds.go.kr HTML 은 robots 전면 차단이라 OpenAPI 로 전환"),
        "provenance": "institution_verbatim", "cadence_days": 7, "content_kind": "prose",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["MFDS_DUR"],
        "api": {
            "url": None,   # 활용신청 뒤 상세기능 탭에서 확인(상세페이지가 JS 렌더라 미확인)
            "params": {}, "items_path": ["body", "items"], "id_field": "", "title_field": "",
            "body_fields": [], "url_template": "", "published_field": "", "disclaimer": _DRUG_DISCLAIMER,
        },
        "note": "기존 HTML 수집기(mfds_safety_letters)는 robots 차단으로 폐기. 필드명은 키 발급 뒤 채운다",
    },
    {
        "id": "mfds_drug_permit", "institution": "식품의약품안전처 의약품 제품허가정보",
        "access": ACCESS_OPENAPI, "fetcher": "datagokr_generic", "key_env": DATA_GO_KR_KEY,
        "license": _lic("datagokr_unrestricted", "2026-10-28", _DATAGOKR.format(15095677),
                        "'제한 없음', 개발 자동승인·운영 심의. 효능효과·용법용량 텍스트 포함 여부는 키 발급 뒤 확인"),
        "provenance": "institution_verbatim", "cadence_days": 30, "content_kind": "codes",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["MFDS_DUR"],
        "api": {"url": None, "params": {}, "items_path": ["body", "items"], "id_field": "", "title_field": "",
                "body_fields": [], "url_template": "", "published_field": "", "disclaimer": _DRUG_DISCLAIMER},
        "note": "전문의약품 포함 허가 품목. e약은요(일반의약품)와 보완",
    },
    {
        "id": "mfds_hff", "institution": "식품의약품안전처 식품안전나라 건강기능식품(품목제조신고·품목분류)",
        "access": ACCESS_OPENAPI_FOODSAFETY, "fetcher": "foodsafety_generic", "key_env": FOODSAFETY_KR_KEY,
        "license": _lic("unknown", "2026-10-28", "https://www.mfds.go.kr/wpge/m_34/de010803l001.do",
                        "식약처 저작권정책(저작권법 24조의2 자유이용, 공공누리 미부착 자료는 담당부서 협의). "
                        "식품안전나라 자체 저작권정책 본문 미확인 → 유형 확인 필요"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_PENDING_VERIFY, "match_url": True, "routes": ["KR_GUIDELINE"],
        "api": {"url": "http://openapi.foodsafetykorea.go.kr/api/{key}/I0030/json/{start}/{end}",
                "services": ["I0030", "I2710"]},
        "note": "주된기능성·섭취시주의사항·섭취방법 설명문. 식품안전나라 회원가입 → OpenAPI 이용신청(키 별도). "
                "웰니스(영양제) 질문 근거",
    },
    {
        "id": "mfds_food_nutrition", "institution": "식품의약품안전처 식품영양성분 DB",
        "access": ACCESS_OPENAPI, "fetcher": "datagokr_generic", "key_env": DATA_GO_KR_KEY,
        "license": _lic("datagokr_unrestricted", "2026-10-28", _DATAGOKR.format(15127578),
                        "'제한 없음', 개발 자동승인·운영 심의"),
        "provenance": "institution_verbatim", "cadence_days": 180, "content_kind": "codes",
        "status": STATUS_PENDING_KEY, "match_url": True, "routes": ["KR_GUIDELINE"],
        "api": {"url": None, "params": {}, "items_path": ["body", "items"], "id_field": "", "title_field": "",
                "body_fields": [], "url_template": "", "published_field": "", "disclaimer": ""},
        "note": "영양성분 수치(코드형). 적재보다 조회형(툴)로 쓰는 편이 맞음 — 우선순위 낮음",
    },
    {
        "id": "cancer_go_kr", "institution": "국립암센터 국가암정보센터",
        "access": ACCESS_HTML, "fetcher": "cancer_go_kr", "key_env": None,
        "license": _lic("terms_restricted", "2026-10-28", "https://www.cancer.go.kr/lay1/S1T633C636/contents.do",
                        "공공누리 아님. 비영리만·출처표시·변경 금지, 정보사용신청서 → 내부심사. 딥링크 불허 조항"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["KDCA"],
        "note": "robots 는 /lay1/… 콘텐츠 허용. 상업 서비스는 정보사용신청(국립암센터) 필요",
    },
    {
        "id": "nhis_health_in", "institution": "국민건강보험공단 건강iN",
        "access": ACCESS_HTML, "fetcher": "nhis_health_in", "key_env": None,
        "license": _lic("unknown", "2026-10-28", "https://www.nhis.or.kr/nhis/etc/wbhaze02900m01.do",
                        "공공누리 개별 표시(건강정보 페이지엔 미부착 → 협의). robots: /nhis/ 전체 Disallow"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_BLOCKED, "match_url": True, "routes": ["KR_GUIDELINE"],
        "note": "hi.nhis.or.kr 는 TLS 인증서 불일치로 접속 불가, 건강정보 API 없음(공단 API 는 검진기관·장기요양기관뿐)",
    },
    {
        "id": "kdca_press", "institution": "질병관리청 보도자료",
        "access": ACCESS_HTML, "fetcher": "kdca_press", "key_env": None,
        "license": _lic("unknown", "2026-10-28", "https://kdca.go.kr/kdca/3509/subview.do",
                        "저작권정책: 제1유형 '표시된' 자료만 자유이용. 보도자료 게시글엔 개별 마크 없음 → 협의 필요"),
        "provenance": "institution_verbatim", "cadence_days": 7, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["KDCA"],
        "note": "목록 /kdca/2848/subview.do, 글 /bbs/kdca/42/{id}/artclView.do. RSS 없음. robots 는 /search.do 만 차단",
    },
    {
        "id": "kdca_nip", "institution": "질병관리청 예방접종도우미(원문)",
        "access": ACCESS_HTML, "fetcher": "kdca_nip", "key_env": None,
        "license": _lic("terms_restricted", "2026-10-28", "https://nip.kdca.go.kr/irhp/index.jsp",
                        "'All rights Reserved', 공공누리 미부착, 저작권정책 페이지 없음 → 질병관리청 예방접종관리과 협의"),
        "provenance": "institution_verbatim", "cadence_days": 90, "content_kind": "prose",
        "status": STATUS_PENDING_LICENSE, "match_url": True, "routes": ["NIP"],
        "note": "기존 nip 시드(요약) 대체 후보. 표준 일정은 law_kr_notice(예방접종 실시기준 별표)로 먼저 확보",
    },
]


def get(source_id: str) -> Optional[Dict]:
    for e in CATALOG:
        if e["id"] == source_id:
            return e
    return None


def ids() -> List[str]:
    return [e["id"] for e in CATALOG]


def license_allows_ingest(license_type: Optional[str]) -> bool:
    return (license_type or "").strip().lower() in INGEST_LICENSES


def effective_status(entry: Dict, env: Optional[Dict[str, str]] = None) -> str:
    """
    사람이 정한 status 에 환경·라이선스 게이트를 더한 실제 상태.
      active 이어도 라이선스가 허용 목록 밖이면 pending_license,
      키 환경변수가 없으면 pending_key.
    """
    env = os.environ if env is None else env
    status = entry.get("status", STATUS_PENDING_VERIFY)
    if status != STATUS_ACTIVE:
        return status
    lic = (entry.get("license") or {}).get("type")
    if entry["id"] != "shortlist" and not license_allows_ingest(lic):
        return STATUS_PENDING_LICENSE
    key_env = entry.get("key_env")
    if key_env and not (env.get(key_env) or "").strip():
        return STATUS_PENDING_KEY
    return STATUS_ACTIVE


def runnable(env: Optional[Dict[str, str]] = None) -> List[Dict]:
    return [e for e in CATALOG if effective_status(e, env) == STATUS_ACTIVE]


def status_table(env: Optional[Dict[str, str]] = None) -> List[Dict]:
    """CLI --status 용 요약 행."""
    rows = []
    for e in CATALOG:
        rows.append({
            "id": e["id"], "institution": e["institution"], "access": e["access"],
            "license": (e.get("license") or {}).get("type"),
            "status": e.get("status"), "effective": effective_status(e, env),
            "key_env": e.get("key_env"), "cadence_days": e.get("cadence_days"),
            "content_kind": e.get("content_kind"),
            "needs": _needs(e, env),
        })
    return rows


def _needs(entry: Dict, env) -> str:
    """사람이 해 줘야 하는 것 한 줄."""
    eff = effective_status(entry, env)
    lic = entry.get("license") or {}
    if eff == STATUS_PENDING_KEY:
        return f"{entry.get('key_env')} 발급·활용신청 ({lic.get('verify_url', '')})"
    if eff == STATUS_PENDING_LICENSE:
        return f"라이선스 결정: {lic.get('type')} — {lic.get('note', '')}"
    if eff == STATUS_PENDING_VERIFY:
        return f"접근·라이선스 확인: {lic.get('verify_url', '')} — {lic.get('note', '')}"
    if eff == STATUS_BLOCKED:
        return f"수집 불가: {lic.get('note', '')}"
    return ""
