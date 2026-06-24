"""
KB 상세 URL 전개기 — 진입/목록 페이지 HTML 에서 주제별 상세 URL 펼치기.

shortlist(docs/plan/22-kb-source-shortlist.md) next-action #2 구현:
KDCA 심뇌혈관(K3)·정신건강포털(K4)·건강위해(K5) 같은 동적 포털은 진입 URL 1개에
하위 상세 페이지가 다수 매달려 있다. 진입 URL 을 그대로 적재하면 저밀도(=품질게이트
스킵)이므로, 진입/목록 HTML 에서 **상세 페이지 링크를 추출 → 정규화 → 필터 → dedup**
하여 실제 콘텐츠 URL 목록을 얻는다.

순수 함수(네트워크/DB 없음, bs4 비의존 — href 정규식 추출). kb_url_normalize·
kb_content_filter 와 합성:
  추출(href) → urljoin(절대화) → normalize_url → 도메인/저밀도/언어/패턴 필터 → dedupe.

실제 fetch 는 호출측(수집기)이 담당. 이 모듈은 "무엇을 가져올지"만 결정.
"""
from __future__ import annotations

import re
from typing import List, Optional, Pattern, Union
from urllib.parse import urljoin, urlsplit

from kb_url_normalize import normalize_url, canonical_key, dedupe_urls
from kb_content_filter import is_low_value_url

# <a ... href="..."> 추출 (단·쌍따옴표, 다른 속성 혼재 허용)
_HREF_RE = re.compile(r'<a\b[^>]*?\bhref\s*=\s*(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)

# 따라가지 않을 스킴
_SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "data:")


def extract_links(html: str) -> List[str]:
    """HTML 의 <a href> 값 목록(원본 문자열, 미정규화)."""
    if not html:
        return []
    return [m.group(2).strip() for m in _HREF_RE.finditer(html)]


def expand_detail_urls(
    html: str,
    base_url: str,
    *,
    same_domain: bool = True,
    include_re: Optional[Union[str, Pattern]] = None,
    exclude_low_value: bool = True,
) -> List[str]:
    """
    진입/목록 페이지 HTML → 정제된 상세 URL 목록.

    Args:
        html:              진입/목록 페이지 HTML
        base_url:          상대경로 절대화 + 동일도메인 판정 기준
        same_domain:       True 면 base 와 다른 호스트 링크 제외(외부 유출 방지)
        include_re:        지정 시 이 정규식에 매칭되는 URL 만 채택
                           (예: r"cntnts_sn=|contentsno=" — 상세 페이지 식별자)
        exclude_low_value: True 면 저밀도/비콘텐츠/언어차단 URL 제외(kb_content_filter)

    Returns:
        정규화·dedup 된 상세 URL 리스트(첫 등장 순서 보존). base_url 자기링크 제외.
    """
    if not html or not base_url:
        return []

    pat = re.compile(include_re) if isinstance(include_re, str) else include_re
    base_host = urlsplit(base_url).netloc.lower()
    base_key = canonical_key(base_url)

    out: List[str] = []
    for href in extract_links(html):
        if not href or href.startswith("#"):
            continue
        if href.lower().startswith(_SKIP_SCHEMES):
            continue

        absu = normalize_url(urljoin(base_url, href))
        sp = urlsplit(absu)
        if sp.scheme not in ("http", "https") or not sp.netloc:
            continue
        if same_domain and sp.netloc.lower() != base_host:
            continue
        if canonical_key(absu) == base_key:   # 진입 페이지 자기링크 제외
            continue
        if exclude_low_value and is_low_value_url(absu):
            continue
        if pat and not pat.search(absu):
            continue
        out.append(absu)

    return dedupe_urls(out)
