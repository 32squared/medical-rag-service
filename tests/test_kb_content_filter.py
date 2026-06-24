"""test_kb_content_filter.py — 콘텐츠 품질 게이트(순수, 네트워크/DB 없음)."""
import kb_content_filter as cf

# 실텍스트 200자+ 정상 건강정보 본문(링크 적음)
_GOOD_MD = (
    "# 고혈압의 이해\n\n"
    "> 출처: 질병관리청 국가건강정보포털 (https://health.kdca.go.kr/x?cntnts_sn=1)\n\n"
    "고혈압은 혈압이 정상 범위보다 지속적으로 높은 상태를 말합니다. "
    "대부분 뚜렷한 증상이 없어 침묵의 질환이라고 불리며, 방치하면 심장과 혈관에 "
    "부담을 주어 심근경색이나 뇌졸중 같은 합병증으로 이어질 수 있습니다. "
    "생활습관 개선으로는 싱겁게 먹기, 규칙적인 유산소 운동, 체중 관리, 금연과 절주가 "
    "도움이 됩니다. 약물 치료가 필요한 경우 의료진과 상담하여 꾸준히 관리하는 것이 "
    "중요하며, 가정에서 정기적으로 혈압을 측정해 추세를 살피는 습관이 권장됩니다.\n"
)


def test_good_content_passes():
    r = cf.assess_content("https://health.kdca.go.kr/healthinfo/gnrlzHealthInfoView.do?cntnts_sn=1", _GOOD_MD)
    assert r["ok"] is True and r["reason"] is None


def test_real_collector_urls_pass():
    for u in [
        "https://nedrug.mfds.go.kr/pbp/CCBBB01/getItemDetail?itemSeq=123",
        "https://www.e-gen.or.kr/egen/first_aid_basics.do?contentsno=16",
        "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=9",
    ]:
        assert cf.assess_content(u, _GOOD_MD)["ok"] is True, u


def test_blocked_language():
    r = cf.assess_content("https://medlineplus.gov/spanish/ency/article/002024.htm", _GOOD_MD)
    assert r == {"ok": False, "reason": "blocked_language"}


def test_low_value_url_patterns():
    for u in [
        "https://www.mentalhealth.go.kr/portal/main/index.do",
        "https://health.kdca.go.kr/healthinfo/biz/health/ccvdInfo/ccvcdInfo/cbvcacdAfterMain.do",
        "https://health.kdca.go.kr/healthhazard/intrcnInfo/hrIntrcnMain",
        "https://www.cdc.gov/vaccines/php/imz-program-resources/partner-websites.html",
        "https://www.mentalhealth.go.kr/portal/health/fac/PotalHealthFacListTab2.do",
    ]:
        r = cf.assess_content(u, _GOOD_MD)
        assert r == {"ok": False, "reason": "low_value_url"}, u


def test_too_short():
    r = cf.assess_content("https://health.kdca.go.kr/v.do?cntnts_sn=2", "# 제목\n\n짧은 안내입니다.")
    assert r == {"ok": False, "reason": "too_short"}


def test_link_farm():
    # 링크 12개, 각 라벨 ~20자, 프로즈 거의 없음 → 링크가 본문을 지배(밀도≈247/12)
    label = "지역 협력 의료기관 공식 홈페이지 바로가기 안내"
    farm = "# 관련 사이트 모음\n\n" + "\n".join(
        f"- [{label}](https://example{i}.kr/page)" for i in range(12)
    )
    r = cf.assess_content("https://example.kr/portal", farm)
    assert r == {"ok": False, "reason": "link_farm"}


# ── 헬퍼 단위 ────────────────────────────────────────────────

def test_text_density_strips_markdown_and_links():
    md = "## 제목\n\n[링크텍스트](https://a.kr) 본문내용 입니다 <b>강조</b>"
    # 링크 URL·HTML 태그·마커 제거 후 '제목 링크텍스트 본문내용 입니다 강조' 의 글자만 카운트
    d = cf.text_density(md)
    assert 10 < d < 30  # 한글/영숫자 글자 수만(공백 제외)


def test_link_count_md_and_html():
    md = "[a](u1) 텍스트 [b](u2) <a href='u3'>c</a>"
    assert cf.link_count(md) == 3


def test_is_low_value_url_combines_language_and_pattern():
    assert cf.is_low_value_url("https://x.kr/foo/es/bar") is True       # 언어
    assert cf.is_low_value_url("https://x.kr/index.do") is True          # 패턴
    assert cf.is_low_value_url("https://x.kr/view.do?cntnts_sn=1") is False
