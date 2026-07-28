"""
vital_input.py — Run Graph `agent_input_field_to_value` 파서 (개인화 입력 계약).

원본 계약(COMPAT-run-graph.md §5): SKIX_A1 에이전트는
  "Vital Signs":      JSON 배열 문자열 — [{bpm, spo2, bpd, bps, fever, stress, create_date}]
  "Air Quality Score": 문자열 (현재 형식 미확정 — 수치 또는 빈 문자열)
  "PHR":               문자열 (현재 "{}" 수준)
을 전달한다.

MVP 정책: 파싱·검증·요약(감사 로그용)만 수행하고 답변 생성에는 미반영.
Phase 1에서 vital_reference_ranges 규칙 엔진에 연결해 [R#] findings로 주입한다
(원시값을 LLM에 직접 보내지 않는 안전 설계 P1 — 마스터플랜).

parse_agent_inputs()는 순수 함수 — 단위테스트 가능.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Vital Signs 허용 필드와 타입 검증 범위 (물리적으로 가능한 값 — 센서 오류 격리용)
_VITAL_FIELDS = {
    "bpm":    {"type": float, "min": 10,   "max": 350},   # 심박수
    "spo2":   {"type": float, "min": 30,   "max": 100},   # 산소포화도 %
    "bps":    {"type": float, "min": 40,   "max": 320},   # 수축기 혈압
    "bpd":    {"type": float, "min": 20,   "max": 220},   # 이완기 혈압
    "fever":  {"type": float, "min": 25,   "max": 45},    # 체온 ℃
    "stress": {"type": float, "min": 0,    "max": 100},   # 스트레스 지수(스케일 미확정)
    "bmi":    {"type": float, "min": 8,    "max": 80},    # 체질량지수(체중계/PHR 유래)
}


def _coerce_record(raw: Dict) -> Optional[Dict]:
    """vital 레코드 1건 검증·정규화. 유효 필드가 하나도 없으면 None."""
    if not isinstance(raw, dict):
        return None
    out: Dict = {}
    for key, spec in _VITAL_FIELDS.items():
        if key not in raw or raw[key] is None:
            continue
        try:
            v = float(raw[key])
        except (TypeError, ValueError):
            continue
        if spec["min"] <= v <= spec["max"]:
            out[key] = v
        # 범위 밖 값은 버리되 기록 (센서 아티팩트)
    if not out:
        return None
    if raw.get("create_date"):
        out["create_date"] = str(raw["create_date"])
    return out


def parse_vital_signs(raw: str) -> List[Dict]:
    """'Vital Signs' 필드(JSON 배열 문자열) → 검증된 레코드 리스트. 실패 시 []."""
    if not raw or not isinstance(raw, str):
        return []
    try:
        data = json.loads(raw)
    except Exception:
        logger.info("[vital] Vital Signs JSON 파싱 실패 — 무시")
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    records = []
    for item in data:
        rec = _coerce_record(item)
        if rec:
            records.append(rec)
    return records


def parse_agent_inputs(agent_input: Optional[Dict]) -> Dict:
    """agent_input_field_to_value 전체 → 구조화 결과 (순수 함수).

    Returns:
        {
          "vital_signs": [ {bpm, spo2, ...}, ... ],   # 검증 통과 레코드만
          "air_quality": str | None,                   # 비어있지 않은 원문
          "phr": str | None,                           # 비어있지 않은 원문 ('{}' 제외)
          "received_fields": [...],                    # 수신된 필드명 (감사용)
        }
    """
    out = {"vital_signs": [], "air_quality": None, "phr": None, "received_fields": []}
    if not isinstance(agent_input, dict):
        return out

    for key, value in agent_input.items():
        out["received_fields"].append(key)

    vs = agent_input.get("Vital Signs")
    if vs:
        out["vital_signs"] = parse_vital_signs(vs)

    aq = (agent_input.get("Air Quality Score") or "").strip() if isinstance(
        agent_input.get("Air Quality Score"), str) else agent_input.get("Air Quality Score")
    if aq:
        out["air_quality"] = str(aq)

    phr = agent_input.get("PHR")
    if isinstance(phr, str):
        phr = phr.strip()
        if phr and phr != "{}":
            out["phr"] = phr
    elif phr:
        out["phr"] = json.dumps(phr, ensure_ascii=False)

    return out


def summarize_for_audit(parsed: Dict) -> str:
    """감사 로그용 비식별 요약 — 원시값 대신 '무엇이 왔는지'만."""
    vs = parsed.get("vital_signs", [])
    parts = []
    if vs:
        fields = sorted({k for r in vs for k in r if k != "create_date"})
        parts.append(f"vitals={len(vs)}건({','.join(fields)})")
    if parsed.get("air_quality"):
        parts.append("air_quality=수신")
    if parsed.get("phr"):
        parts.append("phr=수신")
    return " ".join(parts) if parts else "개인화입력=없음"
