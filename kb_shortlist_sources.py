"""
KB 출처 숏리스트 설정 — docs/plan/25-kb-source-shortlist.md 의 채택 5건(K1~K5).

collect_public_kb.fetch_shortlist 가 이 설정을 읽어 수집한다(설정과 수집 로직 분리).
순수 데이터 + 판정 함수만 — 네트워크/DB 없음.

라이선스 fail-closed (04-kb-expansion-list P4):
  본문 적재는 public_domain / kogl_type1 / cc_by 만 허용.
  'kogl_pending'(공공누리 유형 미확정)은 **수집·적재하지 않고 경고만** 남긴다.
  → 사람이 출처 사이트에서 유형을 확인한 뒤 이 파일의 license 값을
    'kogl_type1' 로 바꾸면 다음 수집부터 자동 포함된다. (유형 2~4 로 판명되면
    본문 적재 불가 — 메타데이터+딥링크 전략으로 별도 처리.)

mode:
  ingest — 해당 URL 1건을 직접 적재 (실콘텐츠 페이지)
  expand — 진입/목록 페이지 → kb_link_expander 로 상세 URL 전개 후 각각 적재
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 본문 적재 허용 라이선스 (P4)
ALLOWED_INGEST_LICENSES = frozenset({"public_domain", "kogl_type1", "cc_by"})


def license_allows_ingest(license_value: Optional[str]) -> bool:
    """P4 판정 — 허용 라이선스만 본문 적재. 미확정/미지정은 False(fail-closed)."""
    return (license_value or "").strip().lower() in ALLOWED_INGEST_LICENSES


# ── 숏리스트 (doc 25 부록 JSON + 수집 메타) ─────────────────────
# url 은 canonical(normalize_url 불변) 형태로 기재한다.
SHORTLIST: List[Dict] = [
    {
        "id": "K1",
        "domain": "infectious_surveillance",
        "url": "https://www.phwr.org/journal/view.html?pn=vol&uid=786&vmd=Full",
        "source_id": "phwr",
        "source_name": "질병관리청 주간 건강과 질병(PHWR)",
        "institution": "질병관리청",
        "jurisdiction": "KR",
        "tier": "primary_kr",
        # 공공누리 유형 미확정 — 확인 후 kogl_type1 로 교체 시 수집 활성화
        "license": "kogl_pending",
        "mode": "ingest",
        "evidence_country": "KR",
    },
    {
        "id": "K2",
        "domain": "cardiovascular",
        "url": "https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5311a5.htm",
        "source_id": "cdc_mmwr",
        "source_name": "CDC MMWR (심혈관 권고 — 보조 출처)",
        "institution": "US CDC",
        "jurisdiction": "US",
        "tier": "secondary",
        "license": "public_domain",
        "mode": "ingest",
        "evidence_country": "US",
    },
    {
        "id": "K3",
        "domain": "cardiovascular",
        "url": "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/cbvcacdAfterMain.do",
        "source_id": "health_kdca",  # 기존 등록 출처 재사용 (kogl_type1 확립)
        "source_name": "KDCA 국가건강정보포털 — 심뇌혈관",
        "institution": "질병관리청",
        "jurisdiction": "KR",
        "tier": "primary_kr",
        "license": "kogl_type1",
        "mode": "expand",
        # 심뇌혈관 섹션 내부 상세만 — 포털 전체로 번지는 것 방지
        "include_re": r"/healthinfo/biz/health/ccvdInfo/",
        "evidence_country": "KR",
    },
    {
        "id": "K4",
        "domain": "mental_health",
        "url": "https://www.mentalhealth.go.kr/portal/main/index.do",
        "source_id": "mentalhealth_kr",
        "source_name": "국가정신건강정보포털",
        "institution": "국립정신건강센터",
        "jurisdiction": "KR",
        "tier": "primary_kr",
        # 공공누리 유형 미확정 — 확인 후 kogl_type1 로 교체 시 수집 활성화
        "license": "kogl_pending",
        "mode": "expand",
        "include_re": r"mentalhealth\.go\.kr/portal/",
        "evidence_country": "KR",
    },
    {
        "id": "K5",
        "domain": "environmental_hazard",
        "url": "https://health.kdca.go.kr/healthhazard/intrcnInfo/hrIntrcnMain",
        "source_id": "health_kdca",  # 기존 등록 출처 재사용
        "source_name": "KDCA 건강위해정보 포털",
        "institution": "질병관리청",
        "jurisdiction": "KR",
        "tier": "primary_kr",
        "license": "kogl_type1",
        "mode": "expand",
        # 건강위해 하위 경로만
        "include_re": r"/healthhazard/",
        "evidence_country": "KR",
    },
]

# 신규 출처의 kb_sources 등록 행 (health_kdca 는 기존 등록 재사용 → 제외)
SOURCE_ROWS: Dict[str, Dict] = {
    "phwr": {
        "id": "phwr",
        "name": "질병관리청 주간 건강과 질병(PHWR)",
        "source_type": "public",
        "license": "kogl_pending",
        "update_frequency": "weekly",
        "is_active": 1,
        "institution": "질병관리청",
        "jurisdiction": "KR",
    },
    "cdc_mmwr": {
        "id": "cdc_mmwr",
        "name": "US CDC MMWR (보조 출처)",
        "source_type": "public",
        "license": "public_domain",
        "update_frequency": "monthly",
        "is_active": 1,
        "institution": "US CDC",
        "jurisdiction": "US",
    },
    "mentalhealth_kr": {
        "id": "mentalhealth_kr",
        "name": "국가정신건강정보포털",
        "source_type": "public",
        "license": "kogl_pending",
        "update_frequency": "monthly",
        "is_active": 1,
        "institution": "국립정신건강센터",
        "jurisdiction": "KR",
    },
}


def ingestible_entries() -> List[Dict]:
    """라이선스 허용(P4) 엔트리만 — 수집기의 실제 대상."""
    return [e for e in SHORTLIST if license_allows_ingest(e.get("license"))]


def pending_entries() -> List[Dict]:
    """라이선스 미확정으로 보류 중인 엔트리 — 운영 로그/보고용."""
    return [e for e in SHORTLIST if not license_allows_ingest(e.get("license"))]
