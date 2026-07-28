"""
symptom_catalog.py — 증상 카탈로그 병합 계층 (Sprint 1 기반 + Sprint 3 보강).

기존 42증상(medical_shared 서브모듈의 consultation_checklists)에
symptom_supplement.json(repo-local additive 증상)을 병합한 단일 카탈로그를 제공한다.
서브모듈을 포크하지 않고 증상을 늘리기 위한 additive 계층(저장소 분리 불변식 준수).

제공:
  load_catalog()            — {symptom_key: item} (42 + 보강)
  load_catalog_by_symptom() — {"symptoms": {...}} (rag_engine CHECKLISTS 호환 형태)
  department_for(key)       — 증상 → 진료과
  all_departments()         — 카탈로그에 등장하는 진료과 집합

병합 규칙: 같은 symptom_key는 서브모듈(기존)이 우선(보강이 기존을 덮어쓰지 않음).
보강 데이터 파일이 없거나 깨져도 기존 42증상으로 무해 동작.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

_SUPPLEMENT_FILENAME = "symptom_supplement.json"

_CATALOG: Dict[str, dict] = {}
_LOADED = False


def _load_base() -> List[dict]:
    """서브모듈 consultation_checklists 원본 list 로드."""
    try:
        import consultation_loader
        return consultation_loader.load_checklists_raw()
    except Exception as e:
        logger.warning("[catalog] 기본 체크리스트 로드 실패: %s", e)
        return []


def _load_supplement() -> List[dict]:
    """repo-local 보강 증상 로드. 없으면 빈 리스트(무해)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _SUPPLEMENT_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("symptoms", []) if isinstance(data, dict) else []
        return [s for s in items if isinstance(s, dict) and s.get("symptom_key")]
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning("[catalog] 보강 증상 로드 실패 (기본만 사용): %s", e)
        return []


def _build() -> Dict[str, dict]:
    global _CATALOG, _LOADED
    if _LOADED:
        return _CATALOG
    _LOADED = True
    catalog: Dict[str, dict] = {}
    for item in _load_base():
        key = item.get("symptom_key")
        if key:
            catalog[key] = item
    added = 0
    for item in _load_supplement():
        key = item["symptom_key"]
        if key not in catalog:          # 기존 우선 — 보강은 덮어쓰지 않음
            catalog[key] = item
            added += 1
    _CATALOG = catalog
    logger.info("[catalog] 증상 카탈로그 %d개 (기본 %d + 보강 %d)",
                len(catalog), len(catalog) - added, added)
    return _CATALOG


def load_catalog() -> Dict[str, dict]:
    """{symptom_key: item} 병합 카탈로그."""
    return dict(_build())


def load_catalog_by_symptom() -> Dict[str, Dict[str, dict]]:
    """rag_engine CHECKLISTS 호환 형태 {"symptoms": {key: item}}."""
    return {"symptoms": dict(_build())}


def department_for(symptom_key: str) -> str:
    """증상 키 → 진료과 (없으면 '')."""
    return (_build().get(symptom_key, {}) or {}).get("department", "")


def all_departments() -> List[str]:
    """카탈로그에 등장하는 진료과 목록 (정렬)."""
    depts = {(v.get("department") or "").strip() for v in _build().values()}
    depts.discard("")
    return sorted(depts)


def reload_catalog() -> int:
    """카탈로그 강제 재로드 (테스트·운영 갱신용). 증상 수 반환."""
    global _CATALOG, _LOADED
    _CATALOG = {}
    _LOADED = False
    return len(_build())
