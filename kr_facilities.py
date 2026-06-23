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

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

HIRA_PHARMACY = "http://apis.data.go.kr/B551182/pharmacyInfoService/getParmacyBasisList"
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


def find_real(kind: str, lat, lon, radius: int = 2000) -> Dict:
    """엔드포인트용 — 실데이터 약국. 병원/약국 외엔 미지원(None)."""
    if kind != "pharmacy":
        return {"supported": False}
    items = nearby_pharmacies(lat, lon, radius=radius)
    if items is None:
        return {"supported": False}     # 키 없음
    return {
        "supported": True, "kind": "pharmacy", "source": "심평원(HIRA) 약국정보",
        "items": items,
        "notice": "심평원 실데이터 · 거리순 중립 안내(특정 약국 추천 아님) · 영업시간은 제공처 목록에 없어 전화 확인 권장",
    }
