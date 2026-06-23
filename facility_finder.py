"""facility_finder.py — 가까운 병원·약국 찾기(거리·영업시간·지금 영업중) (§5.8).

⚠️ 데모 데이터. 실제는 공공 API(응급의료포털 E-Gen·공공데이터포털 약국/병원정보,
data.go.kr 서비스키) 연동 — `find(...)` 구조는 동일, _SAMPLE 만 API 응답으로 교체.
컴플라이언스(§5.8·WC-C6): **거리순 중립 목록** — 특정 병원 추천·영리 알선 아님.
지도 링크는 공개 지도 '검색'(예약·제휴 아님). 응급은 항상 119·E-Gen 우선(I7, referral.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

# 데모 시설 — name, area, dist_m, open/close(HH:MM, 24:00=자정), days('평일'|'매일'), tel, dept
_SAMPLE: Dict[str, List[Dict]] = {
    "hospital": [
        {"name": "역삼연합내과의원", "area": "역삼동", "dist_m": 280, "open": "09:00", "close": "18:30", "days": "평일", "tel": "02-555-0101", "dept": "내과"},
        {"name": "강남365의원", "area": "역삼동", "dist_m": 560, "open": "00:00", "close": "24:00", "days": "매일", "tel": "02-555-0202", "dept": "가정의학과"},
        {"name": "우리가정의학과", "area": "논현동", "dist_m": 1200, "open": "09:30", "close": "17:30", "days": "평일", "tel": "02-555-0303", "dept": "가정의학과"},
    ],
    "pharmacy": [
        {"name": "역삼온누리약국", "area": "역삼동", "dist_m": 150, "open": "09:00", "close": "22:00", "days": "매일", "tel": "02-555-1001"},
        {"name": "건강한약국", "area": "역삼동", "dist_m": 430, "open": "08:30", "close": "19:00", "days": "평일", "tel": "02-555-1002"},
        {"name": "24시명문약국", "area": "강남역", "dist_m": 760, "open": "00:00", "close": "24:00", "days": "매일", "tel": "02-555-1003"},
    ],
}


def _to_min(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def open_now(fac: Dict, now: datetime) -> bool:
    """현재 시각 기준 영업중 여부(요일·영업시간)."""
    if fac.get("days") == "평일" and now.weekday() >= 5:   # 토(5)·일(6)
        return False
    o = _to_min(fac["open"])
    c = _to_min(fac["close"])
    if c <= o:
        c = 24 * 60
    cur = now.hour * 60 + now.minute
    return o <= cur < c


def _dist_label(m: int) -> str:
    return f"{m}m" if m < 1000 else f"{m/1000:.1f}km"


def find(kind: str, now: datetime, region: Optional[str] = None, limit: int = 4) -> List[Dict]:
    """종류(hospital|pharmacy) → 영업중 우선·거리순 시설 목록(거리·영업시간·영업중·지도/전화).

    region(자가입력 동네)은 데모에선 라벨용. 실연동 시 위치 질의에 사용.
    """
    out: List[Dict] = []
    for f in _SAMPLE.get(kind, []):
        d = dict(f)
        d["open_now"] = open_now(f, now)
        d["dist_label"] = _dist_label(f["dist_m"])
        d["hours"] = f"{f['open']}~{f['close']} ({f['days']})"
        d["map_url"] = "https://map.kakao.com/?q=" + f["name"]   # 공개 지도 검색(중립)
        d["tel_url"] = "tel:" + f["tel"].replace("-", "")
        out.append(d)
    out.sort(key=lambda x: (not x["open_now"], x["dist_m"]))     # 영업중 우선, 가까운 순
    return out[:limit]


def find_demo(kind: str, region: Optional[str] = None) -> Dict:
    """엔드포인트용 래퍼 — 현재 시각(서버) 기준 + 데모 고지."""
    items = find(kind, datetime.now(), region=region)
    return {"kind": kind, "region": region or "내 주변", "demo": True, "items": items,
            "notice": "데모 데이터 · 실제 인근 시설은 공공 API(E-Gen·공공데이터포털) 연동 필요 · 거리순 중립 안내(특정 병원 추천 아님)"}
