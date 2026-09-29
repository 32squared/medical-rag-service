"""
seed_reference_ranges.py — 생체신호·환경 공인 참조범위 시드 (KB 확장 P2).

두 가지를 동시에 적재한다:
1. vital_reference_ranges 구조화 테이블 (마이그레이션 010) — 향후 규칙 엔진 lookup용.
   LLM이 기준값을 "생성"하지 못하게 하는 환각 방어의 핵심.
2. KB 문서 (kb_documents/kb_chunks) — 현행 RAG가 즉시 인용할 수 있는 마크다운 본문.

원칙(마스터플랜 결정 #2 반영):
- 모든 구간에 공식 출처·버전·발효연도를 명기한다.
- 본문은 "기준 수치의 사실 정보 + 출처"이며, 개인 측정값의 판정·진단 표현을 쓰지 않는다.
- 문서마다 "진단은 의료기관에서" 안내를 포함한다.

build_reference_rows() / build_reference_documents()는 순수 함수 — DB 없이 테스트 가능.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

_SOURCE_ID = "vital_refs"

_REFS_SOURCE = {
    "id": _SOURCE_ID,
    "name": "공인 생체신호·환경 참조범위 큐레이션",
    "source_type": "guideline",
    "license": "kogl_type1",
    "update_frequency": "yearly",
    "is_active": 1,
}

_DISCLAIMER = (
    "위 수치는 공인 지침의 일반 기준 정보이며, 개인의 상태에 대한 진단이 아닙니다. "
    "측정값의 해석과 진단은 반드시 의료기관에서 확인하시기 바랍니다."
)

# ── 참조범위 정의 (signal × population × locale, 전 항목 공식 출처 명기) ──
_RANGES: List[Dict] = [
    {
        "id": "bp.adult.kr.ksh2022",
        "signal_key": "blood_pressure",
        "population": "adult",
        "locale": "KR",
        "unit": "mm[Hg]",
        "ranges": [
            # rule(자연어) = KB 인용 본문 / bands(기계가독) = vital_rules.lookup_band 소비.
            # label_user = 사용자 노출 중립 3단(안정/주의/경고) — 임상/질환 라벨(label) 비노출(I12).
            {"label": "정상혈압", "rule": "수축기 <120 그리고 이완기 <80",
             "label_user": "안정", "context": "clinic", "combine": "and",
             "bands": [{"axis": "systolic", "max": 120, "max_inclusive": False},
                       {"axis": "diastolic", "max": 80, "max_inclusive": False}]},
            {"label": "주의혈압", "rule": "수축기 120-129 그리고 이완기 <80",
             "label_user": "주의", "context": "clinic", "combine": "and",
             "bands": [{"axis": "systolic", "min": 120, "max": 129, "min_inclusive": True, "max_inclusive": True},
                       {"axis": "diastolic", "max": 80, "max_inclusive": False}]},
            {"label": "고혈압전단계", "rule": "수축기 130-139 또는 이완기 80-89",
             "label_user": "주의", "context": "clinic", "combine": "or",
             "bands": [{"axis": "systolic", "min": 130, "max": 139, "min_inclusive": True, "max_inclusive": True},
                       {"axis": "diastolic", "min": 80, "max": 89, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "고혈압 1기", "rule": "수축기 140-159 또는 이완기 90-99",
             "label_user": "경고", "context": "clinic", "combine": "or",
             "bands": [{"axis": "systolic", "min": 140, "max": 159, "min_inclusive": True, "max_inclusive": True},
                       {"axis": "diastolic", "min": 90, "max": 99, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "고혈압 2기", "rule": "수축기 160 이상 또는 이완기 100 이상",
             "label_user": "경고", "context": "clinic", "combine": "or",
             "bands": [{"axis": "systolic", "min": 160, "min_inclusive": True},
                       {"axis": "diastolic", "min": 100, "min_inclusive": True}]},
            # 가정혈압(home): 시드의 단일 역치(135/85)만 구조화 — 그 미만은 의도적 no_match(거짓안심 비대칭).
            {"label": "가정혈압 고혈압 기준", "rule": "135/85 이상 (진료실 기준과 다름)",
             "label_user": "경고", "context": "home", "combine": "or",
             "bands": [{"axis": "systolic", "min": 135, "min_inclusive": True},
                       {"axis": "diastolic", "min": 85, "min_inclusive": True}]},
        ],
        "source_name": "대한고혈압학회 고혈압 진료지침",
        "source_url": "https://www.koreanhypertension.org",
        "source_version": "KSH 2022",
        "effective_date": "2022",
        "notes": "5분 안정 후 측정, 2회 이상 평균 권장. 1회 측정만으로 판단하지 않음.",
    },
    {
        "id": "bp.adult.us.acc2017",
        "signal_key": "blood_pressure",
        "population": "adult",
        "locale": "US",
        "unit": "mm[Hg]",
        "ranges": [
            {"label": "Normal", "rule": "수축기 <120 그리고 이완기 <80",
             "label_user": "안정", "context": "clinic", "combine": "and",
             "bands": [{"axis": "systolic", "max": 120, "max_inclusive": False},
                       {"axis": "diastolic", "max": 80, "max_inclusive": False}]},
            {"label": "Elevated", "rule": "수축기 120-129 그리고 이완기 <80",
             "label_user": "주의", "context": "clinic", "combine": "and",
             "bands": [{"axis": "systolic", "min": 120, "max": 129, "min_inclusive": True, "max_inclusive": True},
                       {"axis": "diastolic", "max": 80, "max_inclusive": False}]},
            {"label": "Stage 1 Hypertension", "rule": "수축기 130-139 또는 이완기 80-89",
             "label_user": "주의", "context": "clinic", "combine": "or",
             "bands": [{"axis": "systolic", "min": 130, "max": 139, "min_inclusive": True, "max_inclusive": True},
                       {"axis": "diastolic", "min": 80, "max": 89, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "Stage 2 Hypertension", "rule": "수축기 140 이상 또는 이완기 90 이상",
             "label_user": "경고", "context": "clinic", "combine": "or",
             "bands": [{"axis": "systolic", "min": 140, "min_inclusive": True},
                       {"axis": "diastolic", "min": 90, "min_inclusive": True}]},
        ],
        "source_name": "ACC/AHA 고혈압 가이드라인",
        "source_url": "https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065",
        "source_version": "ACC/AHA 2017",
        "effective_date": "2017",
        "notes": "한국(KSH 2022)과 미국(ACC/AHA 2017)의 고혈압 기준이 다름 — 로케일별 기준 적용.",
    },
    {
        "id": "glucose.adult.kr.kda",
        "signal_key": "fasting_glucose",
        "population": "adult",
        "locale": "KR",
        "unit": "mg/dL",
        "ranges": [
            {"label": "정상", "rule": "공복혈당 <100",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "max": 100, "max_inclusive": False}]},
            {"label": "공복혈당장애", "rule": "공복혈당 100-125",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 100, "max": 125, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "당뇨병 기준", "rule": "공복혈당 126 이상 (서로 다른 날 2회 이상 확인 등 진단 기준 충족 필요)",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "min": 126, "min_inclusive": True}]},
        ],
        "source_name": "대한당뇨병학회 당뇨병 진료지침",
        "source_url": "https://www.diabetes.or.kr",
        "source_version": "KDA 진료지침",
        "effective_date": "2023",
        "notes": "8시간 이상 금식 후 측정 기준. 진단은 재검사로 확정 — 1회 수치로 판단하지 않음.",
    },
    {
        "id": "hba1c.adult.kr.kda",
        "signal_key": "hba1c",
        "population": "adult",
        "locale": "KR",
        "unit": "%",
        "ranges": [
            {"label": "정상", "rule": "<5.7",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "max": 5.7, "max_inclusive": False}]},
            {"label": "당뇨병 전단계 범위", "rule": "5.7-6.4",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 5.7, "max": 6.4, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "당뇨병 기준", "rule": "6.5 이상 (진단 기준 충족 필요)",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "min": 6.5, "min_inclusive": True}]},
        ],
        "source_name": "대한당뇨병학회 / ADA Standards of Care",
        "source_url": "https://www.diabetes.or.kr",
        "source_version": "KDA/ADA",
        "effective_date": "2023",
        "notes": "당화혈색소는 2-3개월 평균 혈당을 반영.",
    },
    {
        "id": "fever.child.global.nice143",
        "signal_key": "body_temperature",
        "population": "child",
        "locale": "GLOBAL",
        "unit": "Cel",
        "ranges": [
            {"label": "발열 기준", "rule": "38.0℃ 이상"},
            {"label": "3개월 미만 영아", "rule": "38.0℃ 이상이면 즉시 진료 권고 (연령 자체가 위험 요인)"},
            {"label": "3-6개월", "rule": "39.0℃ 이상이면 진료 권고"},
        ],
        "source_name": "NICE NG143 (5세 미만 발열) / 대한소아청소년과학회",
        "source_url": "https://www.nice.org.uk/guidance/ng143",
        "source_version": "NICE NG143",
        "effective_date": "2019(2021 갱신)",
        "notes": "측정 부위(고막·이마·겨드랑이)에 따라 수치 차이 존재. 동반 증상(처짐·발진·경련·탈수)이 수치보다 중요할 수 있음.",
    },
    {
        "id": "spo2.all.global.who",
        "signal_key": "spo2",
        "population": "all",
        "locale": "GLOBAL",
        "unit": "%",
        "ranges": [
            # 주의: 워치(웰니스 등급) SpO2는 lookup device_grade='wellness'로 deny(I8) — 본 밴드는 의료기기(clinical_near)용.
            {"label": "일반적 정상 범위", "rule": "95-100%",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "min": 95, "max": 100, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "저하 범위", "rule": "90-94% — 의료 상담 권고",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 90, "max": 94, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "중증 저산소혈증", "rule": "90% 미만 — 즉시 응급의료 이용 권고",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "max": 90, "max_inclusive": False}]},
        ],
        "source_name": "WHO 산소요법 기준 / FDA 펄스옥시미터 안전서한",
        "source_url": "https://www.who.int",
        "source_version": "WHO",
        "effective_date": "2021",
        "notes": "손가락 온도·매니큐어·말초순환·피부색에 따른 측정 오차 가능(FDA 안전서한). 수치가 낮게 나오면 손을 따뜻하게 한 뒤 재측정 권장.",
    },
    {
        "id": "temp.adult.global.general",
        "signal_key": "body_temperature",
        "population": "adult",
        "locale": "GLOBAL",
        "unit": "Cel",
        "ranges": [
            {"label": "일반적 정상 범위", "rule": "36.1-37.2℃ 내외 (개인차·일중변동 존재)",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "min": 36.1, "max": 37.2, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "미열 범위", "rule": "37.3-37.9℃",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 37.3, "max": 37.9, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "발열", "rule": "38.0℃ 이상",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "min": 38.0, "min_inclusive": True}]},
        ],
        "source_name": "표준 임상 교과서 통용 기준 (KDCA 건강정보 준용)",
        "source_url": "https://health.kdca.go.kr",
        "source_version": "통용 기준",
        "effective_date": "",
        "notes": "측정 부위·시간대에 따라 0.3-0.6℃ 차이 가능.",
    },
    {
        "id": "pm25.all.kr.cai",
        "signal_key": "pm25",
        "population": "all",
        "locale": "KR",
        "unit": "ug/m3",
        "ranges": [
            {"label": "좋음", "rule": "일평균 0-15"},
            {"label": "보통", "rule": "일평균 16-35"},
            {"label": "나쁨", "rule": "일평균 36-75 — 민감군(호흡기·심혈관 질환자, 어린이, 임신부, 고령자) 장시간 실외활동 자제 권고"},
            {"label": "매우나쁨", "rule": "일평균 76 이상 — 전 인구 실외활동 자제 권고"},
        ],
        "source_name": "환경부 통합대기환경지수(CAI) / 에어코리아",
        "source_url": "https://www.airkorea.or.kr",
        "source_version": "환경부 CAI",
        "effective_date": "2018",
        "notes": "WHO AQG 2021의 PM2.5 24시간 권고기준은 15µg/m³로 한국 '보통' 구간보다 엄격함.",
    },
    {
        "id": "pm10.all.kr.cai",
        "signal_key": "pm10",
        "population": "all",
        "locale": "KR",
        "unit": "ug/m3",
        "ranges": [
            {"label": "좋음", "rule": "일평균 0-30"},
            {"label": "보통", "rule": "일평균 31-80"},
            {"label": "나쁨", "rule": "일평균 81-150"},
            {"label": "매우나쁨", "rule": "일평균 151 이상"},
        ],
        "source_name": "환경부 통합대기환경지수(CAI)",
        "source_url": "https://www.airkorea.or.kr",
        "source_version": "환경부 CAI",
        "effective_date": "2018",
        "notes": "",
    },
    {
        "id": "co2.indoor.kr.iaq",
        "signal_key": "co2_indoor",
        "population": "all",
        "locale": "KR",
        "unit": "[ppm]",
        "ranges": [
            {"label": "다중이용시설 유지기준", "rule": "1,000ppm 이하 (실내공기질 관리법)"},
            {"label": "환기 권고 참고", "rule": "1,000ppm 초과 시 환기 권장 — 졸음·집중력 저하와 관련 보고"},
        ],
        "source_name": "실내공기질 관리법 (다중이용시설 유지기준 준용)",
        "source_url": "https://www.law.go.kr/법령/실내공기질관리법",
        "source_version": "실내공기질관리법",
        "effective_date": "현행",
        "notes": "주택은 법정 적용 대상이 아니며 참고 기준으로 준용. CO2는 환기 상태의 지표.",
    },
    {
        "id": "bmi.adult.kr.ksso",
        "signal_key": "bmi",
        "population": "adult",
        "locale": "KR",
        "unit": "kg/m2",
        "ranges": [
            {"label": "저체중", "rule": "<18.5",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "max": 18.5, "max_inclusive": False}]},
            {"label": "정상", "rule": "18.5-22.9",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "min": 18.5, "max": 22.9, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "비만전단계", "rule": "23-24.9",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 23, "max": 24.9, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "1단계 비만", "rule": "25-29.9",
             "label_user": "주의", "context": "clinic",
             "bands": [{"axis": "value", "min": 25, "max": 29.9, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "2단계 비만", "rule": "30-34.9",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "min": 30, "max": 34.9, "min_inclusive": True, "max_inclusive": True}]},
            {"label": "3단계 비만", "rule": "35 이상",
             "label_user": "경고", "context": "clinic",
             "bands": [{"axis": "value", "min": 35, "min_inclusive": True}]},
        ],
        "source_name": "대한비만학회 비만 진료지침 (아시아-태평양 기준)",
        "source_url": "https://www.kosso.or.kr",
        "source_version": "KSSO",
        "effective_date": "2022",
        "notes": "서양(WHO 일반) 기준은 비만 30 이상으로 한국 기준과 다름 — 로케일별 기준 적용.",
    },
    {
        "id": "hr.adult.global.general",
        "signal_key": "heart_rate",
        "population": "adult",
        "locale": "GLOBAL",
        "unit": "/min",
        "ranges": [
            # 단일 정상범위만 시드 보유 — 범위 밖은 no_match(서맥/빈맥 tier는 미시드 → fail-closed).
            {"label": "안정 시 일반적 범위", "rule": "60-100회/분 (운동선수는 더 낮을 수 있음)",
             "label_user": "안정", "context": "clinic",
             "bands": [{"axis": "value", "min": 60, "max": 100, "min_inclusive": True, "max_inclusive": True}]},
        ],
        "source_name": "표준 임상 교과서 통용 기준",
        "source_url": "",
        "source_version": "통용 기준",
        "effective_date": "",
        "notes": "측정 직전 활동·카페인·스트레스의 영향을 받음. 스트레스 지수·HRV는 공인 임상 참조범위가 없어 웰니스 지표로만 다룸.",
    },
]

# ── 교차신호 조합 근거 KB (vital_rules._CROSS_WHITELIST의 cite_doc_id와 매칭) ──
# 인구집단 수준 일반 연관 사실만 — 개인 귀속·진단 단정 없음(population-level test 통과).
# metadata.cite_doc_id 불변 별칭으로 finding↔KB 결정적 조인(11 §5).
_CROSS_DOCS: List[Dict] = [
    {
        "cite_doc_id": "ref.metabolic.kr",
        "title": "혈압과 체중(비만)의 일반적 연관 안내",
        "topic": "metabolic",
        "body": [
            "체중과 혈압은 일반적으로 함께 살펴보면 도움이 되는 것으로 알려져 있습니다.",
            "비만은 고혈압의 위험요인 중 하나로 보고되며, 체중·허리둘레와 혈압을 함께 관리하는 것이 일반적으로 권장됩니다.",
            "구체적인 평가와 관리 방법은 개인 상태에 따라 다르므로 의료진과 상담이 필요합니다.",
        ],
        "source_name": "대한비만학회 / 대한고혈압학회 일반 정보",
        "source_url": "https://www.kosso.or.kr",
        "source_version": "일반 지침 정보",
        "topic_keywords": ["혈압", "체중", "비만", "대사", "위험요인", "참조범위"],
    },
]


# signal_key → 한국어 표시명 (KB 문서 제목용)
_SIGNAL_NAMES = {
    "blood_pressure": "혈압",
    "fasting_glucose": "공복혈당",
    "hba1c": "당화혈색소(HbA1c)",
    "body_temperature": "체온",
    "spo2": "산소포화도(SpO2)",
    "pm25": "초미세먼지(PM2.5)",
    "pm10": "미세먼지(PM10)",
    "co2_indoor": "실내 이산화탄소(CO2)",
    "bmi": "체질량지수(BMI)",
    "heart_rate": "심박수",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_reference_rows(ranges: List[Dict] = None) -> List[Dict]:
    """참조범위 정의 → vital_reference_ranges 행 dict 리스트 (순수 함수)."""
    ranges = ranges if ranges is not None else _RANGES
    now = _now()
    rows: List[Dict] = []
    for r in ranges:
        rows.append({
            "id": r["id"],
            "signal_key": r["signal_key"],
            "population": r.get("population", "adult"),
            "locale": r.get("locale", "KR"),
            "unit": r["unit"],
            "ranges_json": json.dumps(r["ranges"], ensure_ascii=False),
            "source_name": r["source_name"],
            "source_url": r.get("source_url", ""),
            "source_version": r.get("source_version", ""),
            "effective_date": r.get("effective_date", ""),
            "notes": r.get("notes", ""),
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        })
    return rows


def build_reference_documents(ranges: List[Dict] = None) -> List[Dict]:
    """참조범위 정의 → RAG 인용용 KB 마크다운 문서 (signal_key별 1건, 순수 함수)."""
    ranges = ranges if ranges is not None else _RANGES
    by_signal: Dict[str, List[Dict]] = {}
    for r in ranges:
        by_signal.setdefault(r["signal_key"], []).append(r)

    docs: List[Dict] = []
    for signal_key, items in by_signal.items():
        name = _SIGNAL_NAMES.get(signal_key, signal_key)
        lines = [f"# {name} 공인 참조 기준 안내", ""]
        for r in items:
            locale_label = {"KR": "한국 기준", "US": "미국 기준", "GLOBAL": "국제 기준"}.get(
                r.get("locale", "KR"), r.get("locale", ""))
            pop_label = {
                "adult": "성인", "child": "소아", "all": "전 연령",
                "infant_lt3m": "3개월 미만 영아", "pregnant": "임신부", "elderly": "고령자",
            }.get(r.get("population", "adult"), r.get("population", ""))
            lines.append(f"## {locale_label} ({pop_label}) — 출처: {r['source_name']} ({r.get('source_version','')})")
            lines.append("")
            for rng in r["ranges"]:
                lines.append(f"- {rng['label']}: {rng['rule']}")
            if r.get("notes"):
                lines.append("")
                lines.append(f"참고: {r['notes']}")
            lines.append("")
        lines.append(_DISCLAIMER)
        content_md = "\n".join(lines)

        first = items[0]
        docs.append({
            "title": f"{name} 공인 참조 기준 안내",
            "content_md": content_md,
            "source_id": _SOURCE_ID,
            "source_url": first.get("source_url", ""),
            "metadata": {
                "evidence_level": "A",
                "source_priority": 2,
                "chunk_type": "reference_range",
                "signal_key": signal_key,
                "cite_doc_id": f"ref.{signal_key}.kr",  # 불변 별칭(11 §5) — band finding 조인용
            },
            "evidence_topic": signal_key,
            "regulatory_korea": any(r.get("locale") == "KR" for r in items),
            "topic_keywords": [name, signal_key, "참조범위", "기준", "정상범위"],
        })
    return docs


def build_cross_reference_documents(cross_docs: List[Dict] = None) -> List[Dict]:
    """교차신호 조합 근거 → RAG 인용용 KB 문서 (순수 함수).

    vital_rules._CROSS_WHITELIST의 cite_doc_id가 가리키는 인구집단 수준 일반 연관 문서.
    개인 귀속·진단 단정 없음. metadata.cite_doc_id로 finding과 결정적 조인(11 §5)."""
    cross_docs = cross_docs if cross_docs is not None else _CROSS_DOCS
    docs: List[Dict] = []
    for d in cross_docs:
        lines = [f"# {d['title']}", ""]
        lines.append(f"## 일반 정보 — 출처: {d['source_name']} ({d.get('source_version','')})")
        lines.append("")
        for b in d["body"]:
            lines.append(f"- {b}")
        lines.append("")
        lines.append(_DISCLAIMER)
        docs.append({
            "title": d["title"],
            "content_md": "\n".join(lines),
            "source_id": _SOURCE_ID,
            "source_url": d.get("source_url", ""),
            "metadata": {
                "evidence_level": "A",
                "source_priority": 2,
                "chunk_type": "cross_reference",
                "cite_doc_id": d["cite_doc_id"],
            },
            "evidence_topic": d.get("topic", "cross"),
            "regulatory_korea": True,
            "topic_keywords": d.get("topic_keywords", []),
        })
    return docs


def insert_reference_rows(rows: List[Dict]) -> int:
    """vital_reference_ranges UPSERT (멱등). 테이블 없으면 마이그레이션 안내 후 0 반환."""
    from dbcommon import get_conn, _p
    inserted = 0
    try:
        with get_conn() as (conn, cur):
            for row in rows:
                cols = list(row.keys())
                placeholders = ", ".join(_p() for _ in cols)
                col_list = ", ".join(cols)
                update_cols = [c for c in cols if c not in ("id", "created_at")]
                set_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
                sql = (
                    f"INSERT INTO vital_reference_ranges ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
                )
                cur.execute(sql, tuple(row[c] for c in cols))
                inserted += 1
            conn.commit()
    except Exception as e:
        print(f"[seed_refs] vital_reference_ranges 적재 실패 "
              f"(마이그레이션 010 적용 여부 확인): {str(e)[:120]}", flush=True)
        return 0
    return inserted


def _register_source() -> None:
    """vital_refs 출처 등록(멱등) + priority_rank=2 보강."""
    from kb_ingest import seed_kb_sources
    seed_kb_sources([_REFS_SOURCE])
    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE kb_sources SET priority_rank = 2, jurisdiction = 'KR', "
                f"institution = '공인 지침 큐레이션' WHERE id = {_p()}",
                (_SOURCE_ID,),
            )
    except Exception as e:
        print(f"[seed_refs] priority_rank 보강 생략: {str(e)[:80]}", flush=True)


def seed_reference_ranges(dry_run: bool = False) -> Dict:
    """참조범위 → 구조화 테이블 + KB 문서 적재."""
    rows = build_reference_rows()
    # 교차조합 근거 문서(ref.metabolic.kr)도 같이 적재 — 빌더만 있고 적재가 빠져 있었다
    docs = build_reference_documents() + build_cross_reference_documents()
    summary = {"rows": len(rows), "documents": len(docs), "rows_inserted": 0, "ingested": 0}
    if dry_run:
        summary["dry_run"] = True
        return summary

    _register_source()
    summary["rows_inserted"] = insert_reference_rows(rows)

    import kb_ingest
    for d in docs:
        try:
            kb_ingest.ingest_document(
                title=d["title"], content_md=d["content_md"], source_id=d["source_id"],
                metadata=d["metadata"], evidence_country="KR",
                evidence_topic=d["evidence_topic"], regulatory_korea=d["regulatory_korea"],
                topic_keywords=d["topic_keywords"], source_url=d.get("source_url", ""),
                upsert=True, status="active",
                match_url=False,  # 기관 대표 URL 공유 — 제목으로 식별(kb_ingest 참고)
            )
            summary["ingested"] += 1
        except Exception as e:
            print(f"[seed_refs] ingest 실패 {d['title']}: {str(e)[:100]}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description="생체신호·환경 공인 참조범위 시드")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = seed_reference_ranges(dry_run=args.dry_run)
    print(f"[seed_refs] 결과: {s}", flush=True)


if __name__ == "__main__":
    main()
