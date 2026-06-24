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


# ── E-Gen 약국목록(좌표+요일별 영업시간) ─────────────────────
from datetime import datetime  # noqa: E402

# 실제 getParmacyListInfoInqire 구조(dutyTime{1-6}s/c + wgs84) 기반 — distance 없음(haversine 계산)
_EGEN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header><body><items>
<item><dutyName>가나약국</dutyName><dutyAddr>서울 강남구 테헤란로 1</dutyAddr><dutyTel1>02-111-2222</dutyTel1>
<dutyTime1s>0900</dutyTime1s><dutyTime1c>2200</dutyTime1c><dutyTime6s>0900</dutyTime6s><dutyTime6c>1300</dutyTime6c>
<wgs84Lon>127.0300</wgs84Lon><wgs84Lat>37.5000</wgs84Lat></item>
<item><dutyName>멀리약국</dutyName><dutyAddr>서울 강남구 테헤란로 99</dutyAddr><dutyTel1>02-333-4444</dutyTel1>
<dutyTime1s>0830</dutyTime1s><dutyTime1c>1800</dutyTime1c>
<wgs84Lon>127.0500</wgs84Lon><wgs84Lat>37.5100</wgs84Lat></item>
</items></body></response>"""


def test_parse_egen_list_fields():
    items = kf.parse_egen_list(_EGEN_XML)
    assert [i["name"] for i in items] == ["가나약국", "멀리약국"]   # 입력순(정렬은 haversine 후)
    assert items[0]["lat"] == 37.5 and items[0]["lon"] == 127.03    # float 좌표
    assert items[0]["_times"][1] == ("0900", "2200")


def test_sido_full_normalizes():
    assert kf._sido_full("서울") == "서울특별시"
    assert kf._sido_full("경기") == "경기도"
    assert kf._sido_full("서울특별시") == "서울특별시"


def test_haversine_known_distance():
    d = kf._haversine_m(37.5000, 127.0300, 37.5100, 127.0300)       # 위도 0.01° ≈ 1.11km
    assert 1050 < d < 1170


def test_egen_open_now_weekday_window():
    times = {1: ("0900", "2200")}
    assert kf.egen_open_now(times, datetime(2026, 6, 22, 10, 0)) is True    # 월 10:00
    assert kf.egen_open_now(times, datetime(2026, 6, 22, 23, 0)) is False   # 월 23:00
    assert kf.egen_open_now(times, datetime(2026, 6, 23, 10, 0)) is None    # 화(미등록)


_HOSP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response><header><resultCode>00</resultCode></header><body><items>
<item><yadmNm>역삼종합병원</yadmNm><clCdNm>종합병원</clCdNm><addr>서울 강남구 테헤란로 5</addr><telno>02-100-2000</telno><distance>320</distance><XPos>127.034</XPos><YPos>37.500</YPos><emdongNm>역삼동</emdongNm></item>
<item><yadmNm>멀리병원</yadmNm><clCdNm>병원</clCdNm><addr>서울 강남구 선릉로 9</addr><telno>02-200-3000</telno><distance>1400</distance><XPos>127.05</XPos><YPos>37.51</YPos><emdongNm>대치동</emdongNm></item>
</items></body></response>"""


def test_parse_hospitals_sorts_and_dept():
    its = kf.parse_hospitals(_HOSP_XML)
    assert [i["name"] for i in its] == ["역삼종합병원", "멀리병원"]    # 거리순
    assert its[0]["distance_m"] == 320.0 and its[0]["dept"] == "종합병원"
    assert its[0]["tel"] == "02-100-2000"
    assert its[0]["lat"] == "37.500" and its[0]["lon"] == "127.034"


def test_egen_enrich_distance_hours_badge():
    items = kf.parse_egen_list(_EGEN_XML)
    user = (37.4990, 127.0300)
    for it in items:                                                # 호출측이 거리 부여
        it["distance_m"] = kf._haversine_m(user[0], user[1], it["lat"], it["lon"])
    items.sort(key=lambda x: x["distance_m"])
    e = kf._egen_enrich(items, datetime(2026, 6, 22, 10, 0), limit=2)
    assert e[0]["name"] == "가나약국"                              # 더 가까움
    assert e[0]["open_now"] is True                                # 월 09:00~22:00
    assert e[0]["hours"] == "오늘(월) 09:00~22:00"
    assert e[0]["dist_label"].endswith("m") or e[0]["dist_label"].endswith("km")
