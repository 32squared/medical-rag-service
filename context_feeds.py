"""
context_feeds.py — 시의성 건강 컨텍스트 피드 (KB 확장 P5).

정적 KB와 분리된 실시간/준실시간 컨텍스트 레이어. 답변에 "오늘"의 환경 정보를
입힌다 (예: 호흡기 질문 + 오늘 미세먼지 '나쁨' → 환기·외출 안내 보강).

설계 원칙:
- KB가 아니다: kb_chunks에 적재하지 않고 TTL 캐시로 보관, 프롬프트 컨텍스트로만 주입.
- 등급 판정은 결정적 규칙(환경부 CAI 기준 — vital_reference_ranges와 동일 출처)
  — LLM이 등급을 생성하지 않는다.
- 키 미설정/API 실패 시 빈 컨텍스트 반환 (무해 폴백) — 답변 생성을 막지 않는다.

피드 현황:
- air_quality: 에어코리아 시도별 실시간 측정 (DATA_GO_KR_KEY 필요) ✅
- weather_warning / flu_alert / food_poison: 스키마만 예약 (TODO — 키·계약 확정 후)

순수 함수(grade_pm25/grade_pm10/summarize_air_quality)는 DB/네트워크 없이 테스트 가능.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_AIRKOREA_API = (
    "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
)
_REQUEST_TIMEOUT = 15

# TTL 캐시 (피드 키 → {"data":..., "at": epoch})
_CACHE: Dict[str, Dict] = {}
_TTL_SECONDS = {
    "air_quality": 3600,        # 에어코리아는 시간 단위 갱신
}

_DEFAULT_SIDO = os.environ.get("CONTEXT_FEED_SIDO", "서울")


# ────────────────────────────────────────────────────────────
#  등급 판정 — 환경부 CAI 기준 (결정적 규칙, 출처 명기)
#  근거: vital_reference_ranges 'pm25.all.kr.cai' / 'pm10.all.kr.cai'와 동일
# ────────────────────────────────────────────────────────────

def grade_pm25(value: Optional[float]) -> str:
    """PM2.5 농도(µg/m³) → 환경부 CAI 등급 (순수 함수)."""
    if value is None:
        return "정보없음"
    if value <= 15:
        return "좋음"
    if value <= 35:
        return "보통"
    if value <= 75:
        return "나쁨"
    return "매우나쁨"


def grade_pm10(value: Optional[float]) -> str:
    """PM10 농도(µg/m³) → 환경부 CAI 등급 (순수 함수)."""
    if value is None:
        return "정보없음"
    if value <= 30:
        return "좋음"
    if value <= 80:
        return "보통"
    if value <= 150:
        return "나쁨"
    return "매우나쁨"


def summarize_air_quality(items: List[Dict], sido: str = "") -> Optional[Dict]:
    """
    에어코리아 측정소 항목 리스트 → 지역 평균 요약 (순수 함수).

    Args:
        items: [{'pm25Value': '32', 'pm10Value': '55', 'stationName': ...}, ...]
        sido:  표시용 시도명

    Returns:
        {'sido', 'pm25_avg', 'pm25_grade', 'pm10_avg', 'pm10_grade',
         'station_count', 'source'} 또는 유효 측정값 없으면 None
    """
    pm25_vals: List[float] = []
    pm10_vals: List[float] = []
    for it in items or []:
        for key, acc in (("pm25Value", pm25_vals), ("pm10Value", pm10_vals)):
            raw = (it.get(key) or "").strip()
            if raw and raw != "-":
                try:
                    acc.append(float(raw))
                except ValueError:
                    pass
    if not pm25_vals and not pm10_vals:
        return None
    pm25_avg = round(sum(pm25_vals) / len(pm25_vals), 1) if pm25_vals else None
    pm10_avg = round(sum(pm10_vals) / len(pm10_vals), 1) if pm10_vals else None
    return {
        "sido": sido,
        "pm25_avg": pm25_avg,
        "pm25_grade": grade_pm25(pm25_avg),
        "pm10_avg": pm10_avg,
        "pm10_grade": grade_pm10(pm10_avg),
        "station_count": max(len(pm25_vals), len(pm10_vals)),
        "source": "에어코리아(환경부) 실시간 측정 / CAI 등급 기준",
    }


# ────────────────────────────────────────────────────────────
#  수집 — 에어코리아 (키 미설정 시 무해 폴백)
# ────────────────────────────────────────────────────────────

def fetch_air_quality(sido: str = None, api_key: str = None) -> Optional[Dict]:
    """에어코리아 시도별 실시간 측정 → 요약. 실패/키 없음이면 None."""
    sido = sido or _DEFAULT_SIDO
    api_key = api_key if api_key is not None else os.environ.get("DATA_GO_KR_KEY", "")
    if not api_key or not _HAS_REQUESTS:
        if not api_key:
            logger.debug("[feeds] DATA_GO_KR_KEY 미설정 — air_quality 피드 비활성")
        return None
    try:
        resp = requests.get(
            _AIRKOREA_API,
            params={
                "serviceKey": api_key,
                "returnType": "json",
                "sidoName": sido,
                "numOfRows": 100,
                "pageNo": 1,
                "ver": "1.3",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items = ((data.get("response") or {}).get("body") or {}).get("items") or []
        return summarize_air_quality(items, sido=sido)
    except Exception as e:
        logger.warning("[feeds] air_quality 수집 실패 (피드 생략): %s", e)
        return None


# ────────────────────────────────────────────────────────────
#  공개 API — TTL 캐시 + 프롬프트 렌더링
# ────────────────────────────────────────────────────────────

def get_context_feeds(sido: str = None, force_refresh: bool = False) -> Dict:
    """
    활성 컨텍스트 피드 일괄 조회 (TTL 캐시).

    Returns:
        {"air_quality": {...} | None}  — 키 없거나 실패한 피드는 None
    """
    feeds: Dict = {}
    now = time.time()

    cache_key = f"air_quality:{sido or _DEFAULT_SIDO}"
    cached = _CACHE.get(cache_key)
    if (not force_refresh and cached
            and now - cached["at"] < _TTL_SECONDS["air_quality"]):
        feeds["air_quality"] = cached["data"]
    else:
        data = fetch_air_quality(sido=sido)
        _CACHE[cache_key] = {"data": data, "at": now}
        feeds["air_quality"] = data

    # TODO(P5): weather_warning(기상청 특보), flu_alert(KDCA 유행주의보),
    #           food_poison(식중독지수) — API 키·이용 조건 확정 후 동일 패턴으로 추가
    return feeds


def render_context_for_prompt(feeds: Dict) -> str:
    """
    피드 → 프롬프트 주입용 텍스트. 빈 피드면 빈 문자열 (주입 생략).

    형식은 사실 + 출처만 — 행동 권고 문구는 KB 근거([E#])가 담당한다.
    """
    lines: List[str] = []
    aq = (feeds or {}).get("air_quality")
    if aq:
        parts = []
        if aq.get("pm25_avg") is not None:
            parts.append(f"초미세먼지(PM2.5) {aq['pm25_avg']}µg/m³ '{aq['pm25_grade']}'")
        if aq.get("pm10_avg") is not None:
            parts.append(f"미세먼지(PM10) {aq['pm10_avg']}µg/m³ '{aq['pm10_grade']}'")
        if parts:
            lines.append(
                f"[오늘의 대기질 — {aq.get('sido','')}] " + ", ".join(parts)
                + f" (출처: {aq.get('source','')})"
            )
    return "\n".join(lines)
