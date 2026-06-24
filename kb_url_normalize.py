"""
KB URL 정규화·dedup·언어필터 — ingest 전처리 (순수 함수, 네트워크/DB 없음).

목적: 같은 논리적 문서가 세션/트래킹 파라미터(jsessionid·utm_*·ACSTracking 등)
때문에 서로 다른 URL로 중복 적재되는 것을 막는다. canonical URL로 정규화하면
kb_ingest.ingest_document 의 멱등성 검사(source_id + source_url)가 중복을 잡는다.

설계 원칙(보수적 — 일반 ingest 경로에 배선되므로):
  - scheme/host 만 소문자화. **경로(path) 대소문자는 보존** — 대소문자 구분 서버에서
    서로 다른 페이지를 잘못 병합하지 않기 위함. (shortlist 의 mmwR→mmwr 병합은
    의도적으로 제외: 일반 함수에서 blanket lowercase 는 오병합 위험.)
  - 알려진 트래킹 파라미터만 제거(denylist). 콘텐츠 식별 파라미터(itemSeq·uid·
    cntnts_sn·pn·vmd 등)는 보존 → 깨끗한 URL 은 정규화해도 불변(idempotent).
  - fragment(#...) 제거.
  - 남은 쿼리 파라미터는 정렬 → 파라미터 순서 차이로 인한 중복 방지.

참조: docs/plan/22-kb-source-shortlist.md · 메모리 kb-ingest-hardening.
"""
from __future__ import annotations

import re
from typing import Iterable, List
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# 제거 대상 트래킹/세션 파라미터 (소문자 기준 비교)
_TRACKING_PARAMS = frozenset({
    # 세션
    "jsessionid", "phpsessid", "aspsessionid",
    # data.go.kr / 정부 포털에서 관측된 트래킹(shortlist)
    "acstrackingid", "acstrackinglabel", "deliveryname", "s_cid", "scid",
    # 광고/캠페인
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "igshid", "mc_cid", "mc_eid", "spm",
    # 분석/레퍼럴
    "_ga", "ref", "ref_src",
})

# 경로에 박히는 자바 서블릿 세션 파라미터( ;jsessionid=... ) 제거
_PATH_SESSION_RE = re.compile(r";jsessionid=[^/?#]*", re.IGNORECASE)

# 차단 언어 마커 (경로 세그먼트)
_BLOCKED_LANG_MARKERS = ("/spanish/", "/es/")


def normalize_url(url: str) -> str:
    """
    URL 을 canonical 형태로 정규화. 깨끗한 URL 엔 idempotent(불변).

    - scheme/host 소문자화, 기본 포트(:80/:443) 제거
    - ;jsessionid 등 경로 세션 파라미터 제거
    - 트래킹 쿼리 파라미터 제거 + 남은 파라미터 정렬
    - fragment 제거

    스킴/호스트가 없는 입력(상대 경로 등)은 그대로 반환(보수적).
    """
    if not url or not isinstance(url, str):
        return url or ""
    raw = url.strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        # 상대 경로·스킴 없는 문자열은 정규화하지 않음
        return raw

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    # 경로: 세션 파라미터 제거(대소문자 보존)
    path = _PATH_SESSION_RE.sub("", parts.path)

    # 쿼리: 트래킹 제거 + 정렬
    kept = [
        (k, v)
        for (k, v) in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    kept.sort()
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ""))  # fragment 제거


def is_blocked_language_url(url: str) -> bool:
    """차단 언어 경로(/spanish/, /es/) 포함 여부. 한국 KB 정합성용."""
    if not url:
        return False
    path = urlsplit(url).path.lower()
    probe = path + "/"  # 끝 세그먼트(/es)도 잡도록 보정
    return any(marker in probe for marker in _BLOCKED_LANG_MARKERS)


def canonical_key(url: str) -> str:
    """
    dedup 키 — normalize 후 (쿼리 없을 때만) trailing slash 정규화.
    쿼리가 있으면 경로 끝 슬래시를 건드리지 않음(콘텐츠 식별 위험 회피).
    """
    n = normalize_url(url)
    sp = urlsplit(n)
    if not sp.query and sp.path.endswith("/") and len(sp.path) > 1:
        n = urlunsplit((sp.scheme, sp.netloc, sp.path.rstrip("/"), "", ""))
    return n


def dedupe_urls(urls: Iterable[str]) -> List[str]:
    """
    canonical_key 기준 dedup. **원본 URL**(첫 등장)을 순서 보존하여 반환
    — 실제 fetch 는 원본으로 하되 중복만 제거.
    """
    seen = set()
    out: List[str] = []
    for u in urls:
        key = canonical_key(u)
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out
