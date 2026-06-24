"""
KB 콘텐츠 품질 게이트 — ingest 전 저품질 페이지 스킵 (순수 함수, 네트워크/DB 없음).

shortlist(docs/plan/22-kb-source-shortlist.md) 정제 규칙 구현:
  - 언어 차단: /spanish/·/es/ (kb_url_normalize 재사용)
  - 저밀도 URL 스킵: 포털 메인(index.do·*Main.do)·링크모음(resources·partner-websites)
    ·시설/기관 목록(FacListTab)·검색결과 페이지
  - 본문 밀도: 마크다운 제거 후 실텍스트 최소 길이 미만 스킵
  - 링크팜 차단: 링크 수 대비 실텍스트가 희박하면 스킵

collect_all ingest 루프에서 assess_content() 로 호출. 깨끗한 본문/URL 은 통과.

설계: 거짓양성(정상 콘텐츠 오차단) 최소화를 우선 — 임계값은 보수적.
참조: 메모리 kb-ingest-hardening.
"""
from __future__ import annotations

import re
from typing import Dict

from kb_url_normalize import is_blocked_language_url

# 저밀도/비콘텐츠 URL 패턴 (대소문자 무시)
#  - /index.do, *Main.do : 포털 메인·진입·목록 페이지
#  - /portal/main/ : 포털 메인 경로
#  - hrIntrcnMain : KDCA 건강위해 진입 페이지(상세 전개 필요, 직접적재 부적합)
#  - partner-websites, /resources : 링크모음
#  - FacListTab, facList : 시설/기관 목록
#  - /search, searchResult : 검색 결과 페이지
_LOW_VALUE_URL_RE = re.compile(
    r"(?:"
    r"/index\.do\b"
    r"|main\.do\b"
    r"|/portal/main/"
    r"|hrintrcnmain\b"
    r"|partner-websites"
    r"|/resources\b"
    r"|faclisttab|faclist"
    r"|/search\b|searchresult"
    r")",
    re.IGNORECASE,
)


def _plain_text(content_md: str) -> str:
    """마크다운에서 마커·링크·HTML·URL 을 제거한 평문."""
    if not content_md:
        return ""
    t = content_md
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)   # [텍스트](url)/![alt](url) → 텍스트
    t = re.sub(r"<[^>]+>", " ", t)                       # HTML 태그
    t = re.sub(r"https?://\S+", " ", t)                  # 잔여 URL
    t = re.sub(r"[#>|*`_~\-]", " ", t)                   # 헤더·인용·표·강조·리스트 마커
    return t


def text_density(content_md: str) -> int:
    """실제 의미 글자(한글·영숫자) 수 — 공백/문장부호 제외."""
    return len(re.findall(r"[가-힣A-Za-z0-9]", _plain_text(content_md)))


def link_count(content_md: str) -> int:
    """마크다운/HTML 링크 개수(대략)."""
    if not content_md:
        return 0
    return len(re.findall(r"\]\(", content_md)) + len(re.findall(r"<a\s", content_md, re.IGNORECASE))


def is_low_value_url(url: str) -> bool:
    """언어 차단 또는 저밀도/비콘텐츠 URL 패턴 여부."""
    if not url:
        return False
    return is_blocked_language_url(url) or _LOW_VALUE_URL_RE.search(url) is not None


def assess_content(
    url: str,
    content_md: str,
    min_chars: int = 200,
    link_farm_min_links: int = 10,
    link_farm_chars_per_link: int = 25,
) -> Dict:
    """
    콘텐츠 적재 적합성 판정.

    Returns:
        {'ok': bool, 'reason': str|None}
        reason ∈ {'blocked_language', 'low_value_url', 'too_short', 'link_farm', None}
    """
    if url:
        if is_blocked_language_url(url):
            return {"ok": False, "reason": "blocked_language"}
        if _LOW_VALUE_URL_RE.search(url):
            return {"ok": False, "reason": "low_value_url"}

    density = text_density(content_md)
    if density < min_chars:
        return {"ok": False, "reason": "too_short"}

    links = link_count(content_md)
    if links >= link_farm_min_links and density / links < link_farm_chars_per_link:
        return {"ok": False, "reason": "link_farm"}

    return {"ok": True, "reason": None}
