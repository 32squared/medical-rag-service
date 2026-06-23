"""test_kr_facilities.py — HIRA 약국 응답 파서(순수, 네트워크 없음)."""
import kr_facilities as kf

# 실제 HIRA getParmacyBasisList 응답 구조(역삼동 반경 2km) 기반 픽스처
_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
<body><items>
<item><addr>서울특별시 강남구 강남대로 256</addr><clCdNm>약국</clCdNm><distance>1589.39</distance><emdongNm>대치동</emdongNm><telno>02-522-5925</telno><XPos>127.0335456</XPos><YPos>37.4864916</YPos><yadmNm>메디팜약국</yadmNm><sgguCdNm>강남구</sgguCdNm></item>
<item><addr>서울특별시 강남구 선릉로 424</addr><clCdNm>약국</clCdNm><distance>1226.33</distance><emdongNm>대치동</emdongNm><telno>567-0429</telno><XPos>127.0500875</XPos><YPos>37.5029179</YPos><yadmNm>진성약국</yadmNm><sgguCdNm>강남구</sgguCdNm></item>
<item><addr>서울특별시 서초구 서초대로77길 3</addr><clCdNm>약국</clCdNm><distance>941.69</distance><emdongNm>서초동</emdongNm><telno>02-533-0886</telno><XPos>127.0264971</XPos><YPos>37.4980499</YPos><yadmNm>온누리약국</yadmNm><sgguCdNm>서초구</sgguCdNm></item>
</items></body></response>"""


def test_parse_sorts_by_distance_ascending():
    items = kf.parse_pharmacies(_XML)
    assert [i["name"] for i in items] == ["온누리약국", "진성약국", "메디팜약국"]
    assert items[0]["distance_m"] == 941.69


def test_parse_extracts_fields():
    first = kf.parse_pharmacies(_XML)[0]
    assert first["addr"].startswith("서울특별시 서초구")
    assert first["tel"] == "02-533-0886"
    assert first["lat"] == "37.4980499" and first["lon"] == "127.0264971"
    assert first["area"] == "서초동"


def test_error_code_returns_empty():
    bad = '<response><header><resultCode>30</resultCode></header><body><items></items></body></response>'
    assert kf.parse_pharmacies(bad) == []


def test_enrich_adds_labels_and_honest_hours():
    enriched = kf._enrich(kf.parse_pharmacies(_XML), limit=2)
    assert len(enriched) == 2
    assert enriched[0]["dist_label"] == "942m"          # 941.69 → 942m
    assert enriched[1]["dist_label"] == "1.2km"         # 1226 → 1.2km
    assert enriched[0]["hours"] is None                 # 영업시간 미제공 — 정직
    assert "전화 확인" in enriched[0]["hours_note"]
    assert enriched[0]["map_url"].startswith("http") and enriched[0]["tel_url"].startswith("tel:")


def test_find_real_no_key_unsupported(monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    assert kf.find_real("pharmacy", 37.5, 127.0)["supported"] is False
    assert kf.find_real("hospital", 37.5, 127.0)["supported"] is False
