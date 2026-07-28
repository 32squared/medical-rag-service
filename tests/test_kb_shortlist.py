# -*- coding: utf-8 -*-
"""숏리스트 수집기 테스트 — 설정 정합·라이선스 fail-closed·전개→수집 (네트워크 없음)."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import collect_public_kb as cpk
from kb_shortlist_sources import (
    ALLOWED_INGEST_LICENSES,
    SHORTLIST,
    SOURCE_ROWS,
    ingestible_entries,
    license_allows_ingest,
    pending_entries,
)
from kb_url_normalize import normalize_url


# ── 설정 정합성 ──────────────────────────────────────────────

def test_shortlist_entries_have_required_fields():
    required = {"id", "domain", "url", "source_id", "source_name",
                "institution", "jurisdiction", "tier", "license",
                "mode", "evidence_country"}
    for e in SHORTLIST:
        missing = required - set(e)
        assert not missing, f"{e.get('id')} 누락 필드: {missing}"
        assert e["mode"] in ("ingest", "expand")
        assert e["tier"] in ("primary_kr", "secondary")


def test_shortlist_urls_are_canonical():
    # 설정의 url 은 normalize_url 불변(canonical) 형태여야 dedup 이 안정
    for e in SHORTLIST:
        assert normalize_url(e["url"]) == e["url"], f"{e['id']} url 이 canonical 아님"


def test_expand_entries_have_section_scope():
    # expand 엔트리는 include_re 로 섹션 제한 (포털 전체 크롤 방지)
    for e in SHORTLIST:
        if e["mode"] == "expand":
            assert e.get("include_re"), f"{e['id']} include_re 없음"
            re.compile(e["include_re"])  # 컴파일 가능해야


def test_new_source_ids_have_registration_rows():
    known_existing = {"health_kdca"}  # 기존 kb_sources 등록 재사용
    for e in SHORTLIST:
        if e["source_id"] not in known_existing:
            assert e["source_id"] in SOURCE_ROWS, f"{e['source_id']} 등록 행 없음"


# ── 라이선스 fail-closed (P4) ────────────────────────────────

def test_license_allows_ingest_matrix():
    assert license_allows_ingest("kogl_type1")
    assert license_allows_ingest("public_domain")
    assert license_allows_ingest("cc_by")
    assert license_allows_ingest("KOGL_TYPE1")  # 대소문자 무관
    assert not license_allows_ingest("kogl_pending")
    assert not license_allows_ingest("kogl_type4")
    assert not license_allows_ingest("proprietary")
    assert not license_allows_ingest("")
    assert not license_allows_ingest(None)


def test_pending_and_ingestible_partition():
    ids = {e["id"] for e in SHORTLIST}
    got = {e["id"] for e in ingestible_entries()} | {e["id"] for e in pending_entries()}
    assert got == ids
    # 현재 시점: K1(PHWR)·K4(정신건강포털) = 유형 미확정 보류
    assert {e["id"] for e in pending_entries()} == {"K1", "K4"}


# ── fetch_shortlist (fake session, 네트워크 0) ────────────────

class _FakeResp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, timeout=None, **kw):
        self.calls.append(url)
        if url not in self.pages:
            return _FakeResp("", status=404)
        return _FakeResp(self.pages[url])


_K3_ENTRY = "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/cbvcacdAfterMain.do"
_K3_DETAIL = "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/strokeView.do?cntnts_sn=101"
_K5_ENTRY = "https://health.kdca.go.kr/healthhazard/intrcnInfo/hrIntrcnMain"
_K5_DETAIL = "https://health.kdca.go.kr/healthhazard/intrcnInfo/topicView?sn=7"
_K2_URL = "https://www.cdc.gov/mmwr/preview/mmwrhtml/rr5311a5.htm"

_PAGES = {
    _K3_ENTRY: """
      <html><body>
        <a href="/healthinfo/biz/health/ccvdInfo/ccvcdInfo/strokeView.do;jsessionid=AB12?cntnts_sn=101">뇌졸중</a>
        <a href="/healthinfo/biz/health/ccvdInfo/ccvcdInfo/strokeView.do?cntnts_sn=101">뇌졸중(중복)</a>
        <a href="https://external.example.com/out">외부링크</a>
        <a href="/healthinfo/index.do">포털메인(저밀도)</a>
        <a href="/other/section/page.do">타섹션(include_re 제외)</a>
      </body></html>
    """,
    _K3_DETAIL: (
        "<html><head><title>국가건강정보포털</title></head><body>"
        "<h1>뇌졸중</h1><p>뇌졸중은 뇌혈관이 막히거나 터져 생기는 질환입니다. "
        "증상이 나타나면 즉시 의료기관을 찾아야 합니다.</p></body></html>"
    ),
    _K5_ENTRY: """
      <html><body>
        <a href="/healthhazard/intrcnInfo/topicView?sn=7&jsessionid=ZZ">미세먼지와 건강</a>
      </body></html>
    """,
    _K5_DETAIL: (
        "<html><head><title>건강위해정보</title></head><body>"
        "<h1>미세먼지와 건강</h1><p>미세먼지 농도가 높은 날의 건강 수칙 안내.</p>"
        "</body></html>"
    ),
    _K2_URL: (
        "<html><head><title>MMWR Cardiovascular Recommendations</title></head>"
        "<body><p>Cardiovascular disease prevention recommendations.</p></body></html>"
    ),
}


@pytest.fixture()
def fake_session(monkeypatch):
    monkeypatch.setattr(cpk, "_RATE_LIMIT_SLEEP", 0)
    return _FakeSession(dict(_PAGES))


def test_fetch_shortlist_skips_pending_license_without_fetch(fake_session):
    cpk.fetch_shortlist(limit_per_seed=10, session=fake_session)
    pending_urls = {e["url"] for e in pending_entries()}
    assert not (pending_urls & set(fake_session.calls)), \
        "라이선스 미확정 엔트리는 fetch 자체가 없어야(P4 fail-closed)"


def test_fetch_shortlist_expands_and_collects(fake_session):
    items = cpk.fetch_shortlist(limit_per_seed=10, session=fake_session)
    by_url = {it["source_url"]: it for it in items}

    # K3: jsessionid 변형 dedup → canonical 1건, 외부/타섹션/저밀도 제외
    k3 = [u for u in by_url if "strokeView" in u]
    assert k3 == [normalize_url(_K3_DETAIL)]
    assert "jsessionid" not in k3[0]
    it3 = by_url[k3[0]]
    assert it3["_source_id"] == "health_kdca"
    assert it3["title"] == "뇌졸중"
    assert it3["_evidence_country"] == "KR"
    assert it3["source_checksum"]
    assert "뇌혈관" in it3["content_md"]

    # 외부 도메인은 fetch 도 안 함
    assert all("external.example.com" not in c for c in fake_session.calls)

    # K5 전개 1건
    assert any("topicView" in u for u in by_url)

    # K2: 직접 수집(보조·US)
    it2 = by_url.get(normalize_url(_K2_URL))
    assert it2 is not None
    assert it2["_source_id"] == "cdc_mmwr"
    assert it2["_evidence_country"] == "US"
    assert it2["_source"] == "shortlist"


def test_fetch_shortlist_respects_limit_per_seed(monkeypatch):
    monkeypatch.setattr(cpk, "_RATE_LIMIT_SLEEP", 0)
    # 상세 링크 5개 — cap=2 면 2건만 fetch
    links = "".join(
        f'<a href="/healthinfo/biz/health/ccvdInfo/ccvcdInfo/v.do?cntnts_sn={i}">t{i}</a>'
        for i in range(5)
    )
    pages = {_K3_ENTRY: f"<html><body>{links}</body></html>"}
    for i in range(5):
        pages[f"https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/v.do?cntnts_sn={i}"] = \
            f"<html><body><h1>주제{i}</h1><p>본문</p></body></html>"
    sess = _FakeSession(pages)
    items = cpk.fetch_shortlist(limit_per_seed=2, session=sess)
    k3_items = [it for it in items if "v.do" in it["source_url"]]
    assert len(k3_items) == 2


def test_fetch_shortlist_title_collision_gets_url_tail(monkeypatch):
    monkeypatch.setattr(cpk, "_RATE_LIMIT_SLEEP", 0)
    links = (
        '<a href="/healthinfo/biz/health/ccvdInfo/a.do?sn=1">a</a>'
        '<a href="/healthinfo/biz/health/ccvdInfo/b.do?sn=2">b</a>'
    )
    same = "<html><head><title>같은제목</title></head><body><p>본문</p></body></html>"
    pages = {
        _K3_ENTRY: f"<html><body>{links}</body></html>",
        "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/a.do?sn=1": same,
        "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/b.do?sn=2": same,
    }
    sess = _FakeSession(pages)
    items = cpk.fetch_shortlist(limit_per_seed=10, session=sess)
    titles = [it["title"] for it in items if it["_source_id"] == "health_kdca"]
    assert len(titles) == len(set(titles)), "배치 내 제목 중복은 URL 꼬리로 구분돼야"


def test_extract_html_title_prefers_h1():
    html = "<html><head><title>포털 공통 제목</title></head><body><h1>페이지 제목</h1></body></html>"
    assert cpk._extract_html_title(html) == "페이지 제목"
    assert cpk._extract_html_title("<html><head><title>T</title></head></html>") == "T"
    assert cpk._extract_html_title("", fallback="FB") == "FB"
