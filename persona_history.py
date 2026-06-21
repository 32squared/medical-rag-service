"""
persona_history.py — 페르소나의 종단(시계열) 데이터 생성기 (테스트/시연용).

단일 측정 대신 현실적인 longitudinal 데이터를 결정적으로 생성한다:
  - 바이탈: 매일 측정, 페르소나별 7일~6개월(태그/profile 기반).
  - 건강검진: 연 1회 × 10년.
  - 처방·진료: 5년치(만성 페르소나는 분기, 그 외 연 1~2회).

결정성: 시드 = persona id 해시, 기준일 = PERSONA_ANCHOR_DATE(기본 2026-06-21).
→ 같은 페르소나는 항상 같은 데이터(테스트 가능). 합성 데이터(실데이터 아님).
"""

from __future__ import annotations

import hashlib
import os
import random
from datetime import date, timedelta
from typing import Dict, List

# 물리적으로 가능한 범위(센서 클램프)
_CLAMP = {"bps": (80, 210), "bpd": (45, 130), "bpm": (40, 150), "spo2": (80, 100),
          "fever": (35.0, 41.0), "stress": (0, 100), "bmi": (14, 45)}
_NOISE = {"bps": 4, "bpd": 3, "bpm": 4, "spo2": 0.8, "fever": 0.2, "stress": 8, "bmi": 0.25}
_DEC = {"fever": 1, "bmi": 1}  # 소수 자리, 나머지는 정수

_ACUTE = {"감기", "발열", "미열", "응급", "감염의심", "흉통", "소아", "보호자"}
_CHRONIC = {"고혈압", "당뇨", "시니어", "대사", "흡연", "추세", "산후", "고령", "호흡기", "COPD", "복약"}

_DEPT = {"고혈압": "순환기내과", "당뇨": "내분비내과", "호흡기": "호흡기내과", "COPD": "호흡기내과",
         "불안": "정신건강의학과", "정신민감": "정신건강의학과", "편두통": "신경과",
         "산후": "산부인과", "임신": "산부인과", "감염의심": "감염내과", "흡연": "호흡기내과",
         "대사": "내분비내과", "검진": "가정의학과"}
_MED_NAME = {"antihypertensive": "암로디핀 5mg", "metformin": "메트포르민 500mg",
             "statin": "아토르바스타틴 10mg"}


def _anchor() -> date:
    try:
        return date.fromisoformat(os.environ.get("PERSONA_ANCHOR_DATE", "2026-06-21"))
    except Exception:
        return date(2026, 6, 21)


def _seeded(key: str) -> random.Random:
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF
    return random.Random(h)


def _latest(persona: dict) -> dict:
    v = persona.get("vitals") or []
    return v[-1] if v and isinstance(v[-1], dict) else {}


def _clamp_round(sig: str, v: float) -> float:
    lo, hi = _CLAMP.get(sig, (None, None))
    if lo is not None:
        v = max(lo, min(hi, v))
    return round(v, _DEC.get(sig, 0))


def window_days(persona: dict) -> int:
    """페르소나별 바이탈 측정 창(7~180일)."""
    h = persona.get("history", {}) or {}
    if "days" in h:
        return max(7, min(180, int(h["days"])))
    tags = set(persona.get("tags") or [])
    if tags & _ACUTE:
        return 10
    if tags & _CHRONIC:
        return 180
    return 30


def generate_vitals_series(persona: dict) -> List[Dict]:
    """일 1회 측정 시계열(오래된→최근). 마지막 = 현재 authored 값(엔진 일관성)."""
    base = _latest(persona)
    signals = [k for k in ("bps", "bpd", "bpm", "spo2", "fever", "stress", "bmi")
               if isinstance(base.get(k), (int, float))]
    if not signals:
        return []
    days = window_days(persona)
    h = persona.get("history", {}) or {}
    trend = h.get("trend", {}) or {}          # 창 전체 누적 변화(end - start)
    noise = {**_NOISE, **(h.get("noise", {}) or {})}
    rng = _seeded(persona["id"] + "_vit")
    end = _anchor()
    out = []
    for i in range(days):                      # i=0 가장 오래된, days-1 최근
        frac = i / (days - 1) if days > 1 else 1.0
        d = end - timedelta(days=days - 1 - i)
        rec = {"create_date": d.isoformat() + "T08:00:00"}
        for s in signals:
            endv = base[s]
            delta = trend.get(s, 0)
            mean = endv - delta * (1 - frac)   # 과거 = end-delta, 현재 = end
            rec[s] = _clamp_round(s, mean + rng.gauss(0, noise.get(s, 2)))
        out.append(rec)
    # 마지막 점은 현재 authored 값으로 고정(엔진/그래프 일관성)
    for s in signals:
        out[-1][s] = base[s]
    return out


def _is_diabetic(persona: dict) -> bool:
    tags = set(persona.get("tags") or [])
    return "당뇨" in tags or "type2_diabetes" in (persona.get("phr") or "")


def generate_checkups(persona: dict, years: int = 10) -> List[Dict]:
    """연 1회 건강검진 × 10년(오래된→최근). 만성은 과거가 더 양호→현재로 악화 추세."""
    rng = _seeded(persona["id"] + "_chk")
    end_year = _anchor().year
    base = _latest(persona)
    diabetic = _is_diabetic(persona)
    end_sys = base.get("bps") if isinstance(base.get("bps"), (int, float)) else 122
    end_dia = base.get("bpd") if isinstance(base.get("bpd"), (int, float)) else 80
    end_bmi = base.get("bmi") if isinstance(base.get("bmi"), (int, float)) else 23.5
    end_glu = 124 if diabetic else 94
    end_chol = 205

    def tv(end, gap, frac, sd, dec=0):
        return round(end - gap * (1 - frac) + rng.gauss(0, sd), dec)

    out = []
    for k in range(years):
        frac = k / (years - 1) if years > 1 else 1.0
        yr = end_year - (years - 1 - k)
        row = {
            "year": yr,
            "수축기": int(tv(end_sys, 14, frac, 3)),
            "이완기": int(tv(end_dia, 8, frac, 2)),
            "공복혈당": int(tv(end_glu, 18 if diabetic else 6, frac, 3)),
            "총콜레스테롤": int(tv(end_chol, 12, frac, 7)),
            "BMI": tv(end_bmi, 2.0, frac, 0.3, 1),
        }
        if diabetic:
            row["당화혈색소"] = tv(7.2, 1.1, frac, 0.2, 1)
        out.append(row)
    return out


def _dept_for(persona: dict) -> str:
    tags = persona.get("tags") or []
    for t in tags:
        if t in _DEPT:
            return _DEPT[t]
    return "가정의학과"


def _meds_for(persona: dict) -> List[str]:
    phr = persona.get("phr") or ""
    return [name for code, name in _MED_NAME.items() if code in phr]


def generate_prescriptions(persona: dict, years: int = 5) -> List[Dict]:
    """5년치 진료·처방(오래된→최근). 만성=분기 방문, 그 외=연 1~2회."""
    rng = _seeded(persona["id"] + "_rx")
    end_year = _anchor().year
    tags = set(persona.get("tags") or [])
    chronic = bool(tags & _CHRONIC)
    dept = _dept_for(persona)
    meds = _meds_for(persona)
    per_year = 4 if chronic else (2 if meds else 1)
    reasons = (["정기 추적 관리"] if chronic else
               ["증상 상담", "건강 상담"])
    a = _anchor()
    out = []
    for y in range(years):
        yr = end_year - (years - 1 - y)
        for v in range(per_year):
            month = rng.randint(1, 12)
            day = rng.randint(1, 28)
            try:
                dt = date(yr, month, day)
            except ValueError:
                dt = date(yr, month, 28)
            if dt > a:
                continue  # 기준일 이후(미래) 진료 제외
            drug = meds[v % len(meds)] if meds else None
            out.append({
                "date": dt.isoformat(),
                "dept": dept,
                "reason": reasons[v % len(reasons)],
                "drug": drug,
                "days": 90 if chronic else 5,
            })
    out.sort(key=lambda x: x["date"])
    return out
