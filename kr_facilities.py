"""kr_facilities.py — 실데이터 '가까운 약국' (심평원 HIRA 약국정보서비스, 위치기반).

엔드포인트: B551182/pharmacyInfoService/getParmacyBasisList (xPos=경도, yPos=위도, radius=m)
→ 응답에 distance(m)·WGS84 좌표(XPos/YPos)·주소(addr)·전화(telno)·약국명(yadmNm) 포함.
좌표변환/전량적재 불필요 — API가 거리 직접 반환.

⚠️ 한계: 이 기본목록엔 **영업시간 필드가 없음**(전화 확인 권장). 영업시간 실데이터는
E-Gen 약국(B552657, dutyTime1s~7c) 활용신청 시 보강 가능 — `hours_note`로 정직 표기.
보안: 키는 환경변수 DATA_GO_KR_KEY (커밋 금지). 컴플라(§5.8·WC-C6): 거리순 중립 목록,
특정 약국 추천/영리 알선 아님. 응급은 항상 119·E-Gen 우선(referral.py).
"""
from __future__ import annotations

import math
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

HIRA_PHARMACY = "http://apis.data.go.kr/B551182/pharmacyInfoService/getParmacyBasisList"
# E-Gen(국립중앙의료원) 약국 목록 — 구별 약국 + dutyTime(요일별 영업시간) + WGS84 좌표
EGEN_PHARMACY_LIST = "http://apis.data.go.kr/B552657/ErmctInsttInfoInqireService/getParmacyListInfoInqire"
_WD_KO = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}
# HIRA 단축 시도명 → E-Gen Q0 정식명
_SIDO_FULL = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
              "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
              "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
              "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
              "제주": "제주특별자치도"}
_HOURS_NOTE = "영업시간 정보 없음 · 전화 확인 권장"


def api_key() -> str:
    return (os.environ.get("DATA_GO_KR_KEY") or "").strip()


def _t(el: ET.Element, tag: str) -> str:
    c = el.find(tag)
    return (c.text or "").strip() if c is not None and c.text else ""


def parse_pharmacies(xml_str: str) -> List[Dict]:
    """HIRA XML → 거리순(가까운 순) 약국 목록(순수, 네트워크 없음)."""
    root = ET.fromstring(xml_str)
    if (root.findtext("./header/resultCode") or "00") != "00":
        return []
    out: List[Dict] = []
    for it in root.findall("./body/items/item"):
        try:
            dist = float(_t(it, "distance"))
        except ValueError:
            continue
        out.append({
            "name": _t(it, "yadmNm"),
            "addr": _t(it, "addr"),
            "tel": _t(it, "telno"),
            "distance_m": dist,
            "lat": _t(it, "YPos"),
            "lon": _t(it, "XPos"),
            "area": _t(it, "emdongNm") or _t(it, "sgguCdNm"),
            "gu": _t(it, "sgguCdNm"), "sido": _t(it, "sidoCdNm"),
        })
    out.sort(key=lambda x: x["distance_m"])
    return out


def _enrich(items: List[Dict], limit: int) -> List[Dict]:
    res = []
    for o in items[:limit]:
        m = int(round(o["distance_m"]))
        d = dict(o)
        d["dist_label"] = f"{m}m" if m < 1000 else f"{m / 1000:.1f}km"
        d["hours"] = None
        d["hours_note"] = _HOURS_NOTE
        d["map_url"] = "https://map.kakao.com/?q=" + urllib.parse.quote(o["name"])
        d["tel_url"] = "tel:" + (o["tel"] or "").replace("-", "")
        res.append(d)
    return res


def nearby_pharmacies(lat, lon, radius: int = 2000, limit: int = 8) -> Optional[List[Dict]]:
    """좌표 주변 약국(거리순). 키 없으면 None(호출측이 데모로 폴백)."""
    key = api_key()
    if not key:
        return None
    q = urllib.parse.urlencode({
        "serviceKey": key, "pageNo": 1, "numOfRows": max(limit * 3, 30),
        "xPos": lon, "yPos": lat, "radius": int(radius),
    })
    # HIRA(B551182)는 기본 Python-urllib UA에 무응답(행) → 브라우저 UA 필수
    req = urllib.request.Request(HIRA_PHARMACY + "?" + q,
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=10) as r:
        xml_str = r.read().decode("utf-8")
    return _enrich(parse_pharmacies(xml_str), limit)


# ── E-Gen(국립중앙의료원) 약국 — 거리 + 영업시간(dutyTime) ──────────────
def _now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)   # Cloud Run=UTC → KST


def _fmt_hhmm(s: str) -> str:
    s = (s or "").strip()
    return s[:2] + ":" + s[2:] if len(s) == 4 and s.isdigit() else ""


def egen_open_now(times: Dict[int, tuple], now_kst: datetime) -> Optional[bool]:
    """dutyTime(요일별 시작/종료, HHMM) + 현재 KST → 지금 영업중. 공휴일 미반영."""
    pair = times.get(now_kst.isoweekday())     # 1=월..7=일
    if not pair:
        return None
    s, c = pair
    if not (s and c and s.isdigit() and c.isdigit()):
        return None
    cur, si, ci = now_kst.hour * 100 + now_kst.minute, int(s), int(c)
    if ci <= si:
        ci = 2400
    return si <= cur < ci


def _sido_full(s: str) -> str:
    s = (s or "").strip()
    if s in _SIDO_FULL:
        return _SIDO_FULL[s]
    for k, v in _SIDO_FULL.items():
        if s.startswith(k):
            return v
    return s


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_egen_list(xml_str: str) -> List[Dict]:
    """E-Gen 약국목록 XML → 약국(좌표+요일별 _times, 거리는 호출측 haversine). 순수."""
    root = ET.fromstring(xml_str)
    if (root.findtext("./header/resultCode") or "00") != "00":
        return []
    out: List[Dict] = []
    for it in root.findall("./body/items/item"):
        times = {}
        for n in range(1, 8):                  # 1~7(월~일), 8=공휴일 제외
            s, c = _t(it, f"dutyTime{n}s"), _t(it, f"dutyTime{n}c")
            if s or c:
                times[n] = (s, c)
        try:
            la, lo = float(_t(it, "wgs84Lat")), float(_t(it, "wgs84Lon"))
        except ValueError:
            continue
        out.append({
            "name": _t(it, "dutyName"), "addr": _t(it, "dutyAddr"),
            "tel": _t(it, "dutyTel1"), "lat": la, "lon": lo, "_times": times,
        })
    return out


def _egen_enrich(items: List[Dict], now_kst: datetime, limit: int) -> List[Dict]:
    wd = now_kst.isoweekday()
    res = []
    for o in items[:limit]:
        m = int(round(o["distance_m"]))
        d = {k: v for k, v in o.items() if k != "_times"}
        d["dist_label"] = f"{m}m" if m < 1000 else f"{m / 1000:.1f}km"
        d["open_now"] = egen_open_now(o["_times"], now_kst)   # True/False/None
        pair = o["_times"].get(wd)
        d["hours"] = (f"오늘({_WD_KO[wd]}) {_fmt_hhmm(pair[0])}~{_fmt_hhmm(pair[1])}"
                      if pair and pair[0] and pair[1] else None)
        if d["open_now"] is None:
            d["hours_note"] = "영업시간 정보 확인 필요"
        d["map_url"] = "https://map.kakao.com/?q=" + urllib.parse.quote(o["name"])
        d["tel_url"] = "tel:" + (o["tel"] or "").replace("-", "")
        res.append(d)
    return res


def _egen_gu_pharmacies(sido: str, gu: str, fetch: int = 1000) -> List[Dict]:
    """E-Gen 약국목록(구 전체) → parse_egen_list."""
    q = urllib.parse.urlencode({"serviceKey": api_key(), "Q0": sido, "Q1": gu,
                                "pageNo": 1, "numOfRows": fetch})
    req = urllib.request.Request(EGEN_PHARMACY_LIST + "?" + q,
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return parse_egen_list(r.read().decode("utf-8"))


def egen_nearby_pharmacies(lat, lon, limit: int = 8) -> Optional[List[Dict]]:
    """좌표→구(HIRA 최근접)→그 구 E-Gen 약국 전체→haversine 거리순→영업시간/영업중."""
    if not api_key():
        return None
    near = nearby_pharmacies(lat, lon, radius=1500, limit=1)   # 구 판정용(HIRA)
    if not near:
        return []
    sido, gu = _sido_full(near[0].get("sido")), near[0].get("gu")
    if not (sido and gu):
        return []
    cand = _egen_gu_pharmacies(sido, gu)
    for c in cand:
        c["distance_m"] = _haversine_m(float(lat), float(lon), c["lat"], c["lon"])
    cand.sort(key=lambda x: x["distance_m"])
    return _egen_enrich(cand, _now_kst(), limit)


def find_real(kind: str, lat, lon, radius: int = 2000) -> Dict:
    """실데이터 약국. E-Gen 우선(거리+영업시간) → 실패 시 HIRA(거리만) → 키 없으면 미지원."""
    if kind != "pharmacy" or not api_key():
        return {"supported": False}
    try:                                        # 1) E-Gen — 거리 + 지금영업중
        eg = egen_nearby_pharmacies(lat, lon, limit=8)
        if eg:
            return {"supported": True, "kind": "pharmacy", "real": True,
                    "source": "E-Gen(국립중앙의료원) 약국", "items": eg,
                    "notice": "E-Gen 실데이터 · 거리순 중립 안내(특정 약국 추천 아님) · 영업시간/지금영업중 반영(공휴일 제외, 변동 시 전화 확인)"}
    except Exception:
        pass                                    # 미인가/오류 → HIRA 폴백
    items = nearby_pharmacies(lat, lon, radius=radius)        # 2) HIRA — 거리만
    if items is None:
        return {"supported": False}
    return {"supported": True, "kind": "pharmacy", "real": True,
            "source": "심평원(HIRA) 약국정보", "items": items,
            "notice": "심평원 실데이터 · 거리순 중립 안내(특정 약국 추천 아님) · 영업시간은 제공처 목록에 없어 전화 확인 권장"}
