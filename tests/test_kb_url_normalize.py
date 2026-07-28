"""test_kb_url_normalize.py — URL 정규화·dedup·언어필터(순수, 네트워크/DB 없음)."""
import kb_url_normalize as kn


# ── normalize_url ───────────────────────────────────────────

def test_clean_url_is_idempotent():
    """트래킹/fragment 없는 깨끗한 URL 은 정규화해도 불변."""
    u = "https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail?itemSeq=123"
    assert kn.normalize_url(u) == u


def test_strip_query_jsessionid():
    u = "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=42&jsessionid=ABC123"
    assert kn.normalize_url(u) == "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=42"


def test_strip_path_jsessionid():
    """자바 서블릿 ;jsessionid=... 경로 파라미터 제거."""
    u = "https://health.kdca.go.kr/healthinfo/view.do;jsessionid=XYZ?cntnts_sn=42"
    assert kn.normalize_url(u) == "https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=42"


def test_strip_tracking_params_acs_delivery_scid_utm():
    u = ("https://www.cdc.gov/mmwr/volumes/72/wr/mm7219e1.htm"
         "?ACSTrackingID=USCDC_921&ACSTrackingLabel=x&deliveryName=DM1&s_cid=abc&utm_source=news")
    assert kn.normalize_url(u) == "https://www.cdc.gov/mmwr/volumes/72/wr/mm7219e1.htm"


def test_content_params_preserved_and_sorted():
    """콘텐츠 식별 파라미터(pn·uid·vmd)는 보존하되 정렬로 안정화."""
    u = "https://www.phwr.org/journal/view.html?vmd=Full&uid=786&pn=vol&jsessionid=Z"
    assert kn.normalize_url(u) == "https://www.phwr.org/journal/view.html?pn=vol&uid=786&vmd=Full"


def test_fragment_dropped_and_host_lowercased():
    u = "https://Health.KDCA.go.KR/info/Page.do?cntnts_sn=7#section3"
    # host 소문자, fragment 제거, **경로 대소문자 보존**
    assert kn.normalize_url(u) == "https://health.kdca.go.kr/info/Page.do?cntnts_sn=7"


def test_path_case_preserved():
    """대소문자 구분 서버 보호 — 경로는 소문자화하지 않는다."""
    u = "https://www.cdc.gov/MMWR/preview/RR5311a5.htm"
    assert kn.normalize_url(u) == u


def test_default_ports_removed():
    assert kn.normalize_url("http://e-gen.or.kr:80/egen/x.do") == "http://e-gen.or.kr/egen/x.do"
    assert kn.normalize_url("https://e-gen.or.kr:443/egen/x.do") == "https://e-gen.or.kr/egen/x.do"


def test_param_order_independent_canonical():
    """파라미터 순서만 다른 두 URL → 동일 canonical."""
    a = "https://s.kr/v.do?a=1&b=2"
    b = "https://s.kr/v.do?b=2&a=1"
    assert kn.normalize_url(a) == kn.normalize_url(b)


def test_empty_and_relative_passthrough():
    assert kn.normalize_url("") == ""
    assert kn.normalize_url(None) == ""
    assert kn.normalize_url("/relative/path?x=1") == "/relative/path?x=1"


# ── is_blocked_language_url ──────────────────────────────────

def test_blocked_language_spanish_and_es():
    assert kn.is_blocked_language_url("https://medlineplus.gov/spanish/ency/article/002024.htm") is True
    assert kn.is_blocked_language_url("https://www.cdc.gov/fever/es/estadisticas.html") is True
    # 경로 끝 세그먼트 /es 도 차단
    assert kn.is_blocked_language_url("https://www.cdc.gov/fever/es") is True


def test_blocked_language_no_false_positive():
    assert kn.is_blocked_language_url("https://medlineplus.gov/espanol/page.htm") is False
    assert kn.is_blocked_language_url("https://health.kdca.go.kr/healthinfo/view.do?cntnts_sn=1") is False
    assert kn.is_blocked_language_url("") is False


# ── canonical_key / dedupe_urls ──────────────────────────────

def test_canonical_key_trailing_slash_only_without_query():
    assert kn.canonical_key("https://s.kr/portal/") == "https://s.kr/portal"
    # 쿼리 있으면 슬래시 보존
    assert kn.canonical_key("https://s.kr/portal/?x=1") == "https://s.kr/portal/?x=1"


def test_dedupe_collapses_tracking_variants_preserves_first():
    urls = [
        "https://health.kdca.go.kr/v.do?cntnts_sn=42",
        "https://health.kdca.go.kr/v.do?cntnts_sn=42&jsessionid=AAA",  # 중복(트래킹만 다름)
        "https://health.kdca.go.kr/v.do?cntnts_sn=99",                 # 다른 문서
    ]
    out = kn.dedupe_urls(urls)
    assert out == [
        "https://health.kdca.go.kr/v.do?cntnts_sn=42",   # 첫 등장 원본 보존
        "https://health.kdca.go.kr/v.do?cntnts_sn=99",
    ]
