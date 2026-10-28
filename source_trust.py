"""
source_trust.py — KB 출처의 출처 성격(provenance)과 "공인 기관 출처만" 검색 모드.

배경(2026-10-28, docs/plan/29): 비의료 건강관리서비스 가이드라인의 공신력 정의는
① 공적 기관·학회가 감수한 정보 ② 다수 전문가가 인정하는 검증된 정보 둘뿐이다.
자체 KB 에는 기관 원문을 그대로 가져온 출처와 우리가 요약·작성한 출처가 섞여 있어,
검색 단계에서 전자만 쓰는 모드를 둔다. 데이터는 지우지 않는다(상태·행 불변).

출처 성격(provenance):
  institution_verbatim — 공공 기관 사이트·OpenAPI 에서 받은 원문 그대로
  official_record      — 고시·법령 원문 전사(저작권법 7조 비보호 저작물). 문장을 고쳐 쓴
                         요약은 여기 넣지 않는다(curated_summary) — 2026-10-28 기준 해당 출처 없음
  curated_summary      — 공공 원문을 우리가 요약·재구성(감수 기록 없음)
  self_authored        — 자체 작성(의사 자문 반영 포함, 감수자·감수일 기록 없음)
  generated            — LLM 생성
  internal_policy      — 내부 규칙 문서(의학 정보 아님)
  third_party          — 민간·학술 색인 등 기관 감수가 아닌 것(PubMed 색인 포함)
  unknown              — 등록되지 않은 출처(fail-closed: 신뢰 모드에서 제외)

신뢰 모드(trusted-only)에서 쓰는 것은 institution_verbatim·official_record 뿐이다.

환경변수:
  RAG_TRUSTED_SOURCES_ONLY — 기본 on. "0|false|no|off" 로 끄면 기존 행동(전체 출처).

라이선스(공공누리 유형·상업 이용 가능 여부)는 여기서 다루지 않는다 — kb_sources.license 와
docs/plan/24-dev-backlog.md 「라이선스」절이 정본이고, 사람·법무 결정 사항이다.
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

INSTITUTION_VERBATIM = "institution_verbatim"
OFFICIAL_RECORD = "official_record"
CURATED_SUMMARY = "curated_summary"
SELF_AUTHORED = "self_authored"
GENERATED = "generated"
INTERNAL_POLICY = "internal_policy"
THIRD_PARTY = "third_party"
UNKNOWN = "unknown"

TRUSTED_PROVENANCES = frozenset({INSTITUTION_VERBATIM, OFFICIAL_RECORD})

# source_id → (표시 기관명, provenance, 관할)
# 표시 기관명은 답변·프롬프트의 「출처: …」 에 그대로 쓰이므로 기관 공식 명칭으로 적는다.
SOURCE_REGISTRY: Dict[str, Dict[str, str]] = {
    # ── 국내 공공 기관 원문 ──
    "health_kdca":    {"name": "질병관리청 국가건강정보포털", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "kdca":           {"name": "질병관리청", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "kdca_api":       {"name": "질병관리청 공공데이터 OpenAPI(감염병·예방접종)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "hira_kdca":      {"name": "건강보험심사평가원·질병관리청 공개 자료", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "hira":           {"name": "건강보험심사평가원", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "hira_dur":       {"name": "건강보험심사평가원 DUR", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "mfds":           {"name": "식품의약품안전처 의약품안전나라", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "mfds_dur":       {"name": "식품의약품안전처 DUR 품목정보", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "mfds_drug_info": {"name": "식품의약품안전처 e약은요", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "nemc":           {"name": "중앙응급의료센터 응급의료포털(E-Gen)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "phwr":           {"name": "질병관리청 주간 건강과 질병(PHWR)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    "mentalhealth_kr": {"name": "국립정신건강센터 국가정신건강정보포털", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "KR"},
    # ── 고시·법령 — 현재 시드는 원문 전사가 아니라 우리가 다시 쓴 요약이라 신뢰 모드에서 제외 ──
    # seed_checkup_criteria_kb: 기준 수치는 고시 [별표 4]·별첨에서 옮겼지만 "문장은 쉬운 말로 다시 썼다"
    #   + 자체 안전 문장. 별표 원문을 그대로 적재하면 그 출처를 OFFICIAL_RECORD 로 등록한다(후속).
    # seed_legal_kb: "핵심 취지를 큐레이션" + 'AI 포함' 같은 적용 해석이 들어 있다.
    "checkup_std_kr": {"name": "국가건강검진 판정기준 요약(보건복지부 고시 기준 수치)", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    "kr_law":         {"name": "의료법·개인정보보호법 핵심 조항 요약", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    # ── 해외 공공·전문기관 원문(보조) ──
    "cdc_mmwr":       {"name": "미국 질병통제예방센터(CDC) MMWR", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "US"},
    "cdc":            {"name": "미국 질병통제예방센터(CDC)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "US"},
    "who":            {"name": "세계보건기구(WHO)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "INTL"},
    "nice":           {"name": "영국 NICE", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "UK"},
    "uspstf":         {"name": "미국 예방서비스특별위원회(USPSTF)", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "US"},
    "dailymed":       {"name": "미국 FDA DailyMed", "provenance": INSTITUTION_VERBATIM, "jurisdiction": "US"},
    # ── 공공 원문을 우리가 요약·재구성(감수 기록 없음) ──
    "nip":            {"name": "질병관리청 예방접종도우미(국가예방접종) 요약", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    "lifecycle_kr":   {"name": "공공 건강정보 큐레이션(암·정신건강·임신·노인·희귀·만성질환)", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    "vital_refs":     {"name": "생체신호·환경 참조범위 큐레이션", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    "safety_kr":      {"name": "가정 안전·중독·소아 응급 큐레이션", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    "navigation_kr":  {"name": "의료 이용 안내 큐레이션", "provenance": CURATED_SUMMARY, "jurisdiction": "KR"},
    # ── 자체 작성 ──
    "consultation_seed":      {"name": "자체 제작 증상 문진 체크리스트(의사 자문 반영)", "provenance": SELF_AUTHORED, "jurisdiction": "KR"},
    "consultation_checklist": {"name": "자체 제작 증상별 문진 가이드(의사 자문 반영)", "provenance": SELF_AUTHORED, "jurisdiction": "KR"},
    "internal_md":    {"name": "의사 직접 작성 콘텐츠", "provenance": SELF_AUTHORED, "jurisdiction": "KR"},
    "kmle_seed":      {"name": "KMLE 발췌", "provenance": THIRD_PARTY, "jurisdiction": "KR"},
    # ── 생성·내부 규칙 ──
    "gpt_generated_v1":   {"name": "LLM 자동 생성 의학 정보(의사 검수 필요)", "provenance": GENERATED, "jurisdiction": "KR"},
    "guideline_internal": {"name": "의료법 준수 내부 기준", "provenance": INTERNAL_POLICY, "jurisdiction": "KR"},
    "guideline":          {"name": "내부 지침", "provenance": INTERNAL_POLICY, "jurisdiction": "KR"},
    # ── 학술 색인·논문(기관 감수 아님) ──
    "pubmed":   {"name": "PubMed 색인 논문", "provenance": THIRD_PARTY, "jurisdiction": "INTL"},
    "pmc_oa":   {"name": "PubMed Central 공개 논문", "provenance": THIRD_PARTY, "jurisdiction": "INTL"},
    "cochrane": {"name": "Cochrane 체계적 문헌고찰", "provenance": THIRD_PARTY, "jurisdiction": "INTL"},
}

_ENV_FLAG = "RAG_TRUSTED_SOURCES_ONLY"
_FALSY = ("0", "false", "no", "off")


def trusted_sources_only() -> bool:
    """공인 기관 출처만 검색하는 모드인지. 기본 on — 끄려면 RAG_TRUSTED_SOURCES_ONLY=0."""
    return os.environ.get(_ENV_FLAG, "1").strip().lower() not in _FALSY


def provenance_of(source_id: Optional[str]) -> str:
    entry = SOURCE_REGISTRY.get((source_id or "").strip().lower())
    return entry["provenance"] if entry else UNKNOWN


def is_trusted_source(source_id: Optional[str]) -> bool:
    """등록되지 않은 출처는 신뢰하지 않는다(fail-closed)."""
    return provenance_of(source_id) in TRUSTED_PROVENANCES


def trusted_source_ids() -> List[str]:
    return sorted(sid for sid, e in SOURCE_REGISTRY.items() if e["provenance"] in TRUSTED_PROVENANCES)


def source_display_name(source_id: Optional[str]) -> str:
    """답변·프롬프트의 「출처: …」 표기용 기관명. 미등록이면 id 그대로."""
    sid = (source_id or "").strip()
    entry = SOURCE_REGISTRY.get(sid.lower())
    return entry["name"] if entry else (sid or "unknown")


def source_jurisdiction(source_id: Optional[str]) -> str:
    entry = SOURCE_REGISTRY.get((source_id or "").strip().lower())
    return entry["jurisdiction"] if entry else "KR"


def restrict_source_types(source_types: Optional[Iterable[str]]) -> Optional[List[str]]:
    """
    검색 source_id 필터에 신뢰 모드를 적용한다.

    - 모드 off → 입력 그대로(None 이면 None = 전체).
    - 모드 on, 입력 None → 신뢰 출처 전체 목록.
    - 모드 on, 입력 있음 → 입력 ∩ 신뢰 출처. 교집합이 비면 **빈 리스트**를 돌려주며,
      호출자는 빈 리스트를 '검색하지 않음'으로 다뤄야 한다(검색 함수는 빈 필터를
      '전체'로 보므로 그대로 넘기면 안 된다).
    """
    if not trusted_sources_only():
        return list(source_types) if source_types is not None else None
    if source_types is None:
        return trusted_source_ids()
    return [s for s in source_types if is_trusted_source(s)]


def describe() -> Dict[str, object]:
    """관리 API·로그용 요약."""
    return {
        "trusted_sources_only": trusted_sources_only(),
        "trusted_source_ids": trusted_source_ids(),
        "excluded_source_ids": sorted(
            sid for sid, e in SOURCE_REGISTRY.items() if e["provenance"] not in TRUSTED_PROVENANCES
        ),
        "provenance": {sid: e["provenance"] for sid, e in SOURCE_REGISTRY.items()},
    }
