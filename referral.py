"""referral.py — 시설 안내(병원·약국·진료과) (순수 함수).

정본: docs/plan/18-wellness-coaching.md §5.8.
핵심선: **중립·공공출처·비영리까지만** — 특정 병원 추천·영리 알선 금지(의료법 27조3항·WC-C6).
응급은 항상 119·응급실 우선(I7). 진료과는 단정 아닌 '일반적으로 관련된 과' 정보 + 최종판단 의료진.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 공공 디렉터리(검토 대상 출처) — 특정 사립기관 아님
PUBLIC: Dict[str, Dict] = {
    "emergency": {"name": "응급의료포털 E-Gen", "url": "https://www.e-gen.or.kr",
                  "desc": "가까운 응급실·당직 의료기관(국립중앙의료원)"},
    "hospital": {"name": "건강보험심사평가원 병원찾기", "url": "https://www.hira.or.kr",
                 "desc": "공공 의료기관 정보"},
    "pharmacy": {"name": "약학정보원 약국찾기", "url": "https://www.health.kr",
                 "desc": "공공 약국 정보"},
}

# 증상→일반적으로 관련된 진료과(단정 아님, 정보 제공)
_DEPT = [
    ("혈압", "내과(순환기)"), ("가슴", "내과(순환기)"), ("심장", "내과(순환기)"),
    ("혈당", "내과(내분비)"), ("당뇨", "내과(내분비)"),
    ("두통", "신경과"), ("어지럼", "신경과"),
    ("관절", "정형외과"), ("허리", "정형외과"),
    ("피부", "피부과"), ("눈", "안과"), ("기침", "호흡기내과"),
]


def referral(band: Optional[str] = None, intent: Optional[str] = None,
             kind: Optional[str] = None) -> Dict:
    """밴드·intent·종류 → 시설 안내(중립 공공출처). 응급이면 119 우선.

    Returns: {urgent, message, links:[{name,url,desc}]}
    """
    if intent == "emergency" or band == "응급":
        return {"urgent": True,
                "message": "응급 증상이면 즉시 119 또는 응급실로 연락하세요",
                "links": [PUBLIC["emergency"]]}
    links: List[Dict] = []
    if kind in (None, "hospital"):
        links.append(PUBLIC["hospital"])
    if kind in (None, "pharmacy"):
        links.append(PUBLIC["pharmacy"])
    msg = "가까운 곳은 아래 공공 정보로 찾아보세요 (특정 병원 추천이 아닌 중립 안내예요)"
    if band == "경고":
        msg = "진료를 우선 고려하시고, " + msg
    return {"urgent": False, "message": msg, "links": links}


def department_hint(text: str) -> Optional[str]:
    """증상 텍스트 → '일반적으로 관련된 진료과' 정보(단정 아님). 없으면 None."""
    for kw, dept in _DEPT:
        if kw in (text or ""):
            return f"이런 증상은 보통 {dept}에서 봅니다 — 최종 판단은 의료진과 상의하세요"
    return None


def is_neutral(links: List[Dict]) -> bool:
    """WC-C6 — 노출 링크가 전부 공공 디렉터리(특정 사립기관 아님)인지 검증."""
    allowed = {v["url"] for v in PUBLIC.values()}
    return all(l.get("url") in allowed for l in (links or []))
