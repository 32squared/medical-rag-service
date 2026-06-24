"""test_kb_link_expander.py — 상세 URL 전개기(순수, 네트워크/DB 없음)."""
import kb_link_expander as lx

_BASE = "https://health.kdca.go.kr/healthinfo/list.do"

# KDCA 목록 페이지를 모사 — 상세 링크 + 네비/푸터/외부/저밀도 잡음 혼재
_HTML = """
<html><body>
<nav><a href="/portal/main/index.do">메인</a></nav>
<ul class="list">
  <li><a href="/healthinfo/view.do?cntnts_sn=101">뇌졸중</a></li>
  <li><a href="/healthinfo/view.do?cntnts_sn=102&jsessionid=ABC">심근경색</a></li>
  <li><a href='view.do?cntnts_sn=103'>고혈압</a></li>
  <li><a href="/healthinfo/view.do?cntnts_sn=101&utm_source=news">뇌졸중(중복)</a></li>
  <li><a href="https://other.kr/view.do?cntnts_sn=999">외부도메인</a></li>
  <li><a href="/portal/health/fac/PotalHealthFacListTab2.do">기관목록</a></li>
  <li><a href="#top">맨위로</a></li>
  <li><a href="javascript:void(0)">스크립트</a></li>
  <li><a href="mailto:a@b.kr">메일</a></li>
  <li><a href="https://health.kdca.go.kr/healthinfo/list.do">현재목록(자기링크)</a></li>
</ul>
<footer><a href="https://www.cdc.gov/vaccines/partner-websites.html">파트너</a></footer>
</body></html>
"""


def test_expand_filters_normalizes_dedups():
    out = lx.expand_detail_urls(_HTML, _BASE, include_re=r"cntnts_sn=")
    assert out == [
        "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=101",
        "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=102",  # jsessionid 제거
        "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=103",  # 상대경로 절대화
    ]
    # 외부도메인·자기링크·#·js·mailto·저밀도(FacListTab)·중복(utm) 모두 제외


def test_same_domain_false_allows_external():
    out = lx.expand_detail_urls(_HTML, _BASE, include_re=r"cntnts_sn=", same_domain=False)
    assert "https://other.kr/view.do?cntnts_sn=999" in out


def test_exclude_low_value_false_includes_portal_main():
    out = lx.expand_detail_urls(_HTML, _BASE, exclude_low_value=False)
    assert "https://health.kdca.go.kr/portal/main/index.do" in out


def test_low_value_excluded_by_default():
    out = lx.expand_detail_urls(_HTML, _BASE)
    assert all("index.do" not in u and "FacListTab" not in u for u in out)
    assert "https://www.cdc.gov/vaccines/partner-websites.html" not in out


def test_self_link_excluded():
    out = lx.expand_detail_urls(_HTML, _BASE, exclude_low_value=False)
    assert _BASE not in out  # 진입 페이지 자기링크 제외


def test_extract_links_basic():
    links = lx.extract_links('<a href="/a">x</a> 텍스트 <A HREF=\'/b?q=1\'>y</A>')
    assert links == ["/a", "/b?q=1"]


def test_empty_inputs():
    assert lx.expand_detail_urls("", _BASE) == []
    assert lx.expand_detail_urls(_HTML, "") == []
    assert lx.extract_links("") == []
