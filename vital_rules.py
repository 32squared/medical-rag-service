"""
vital_rules.py — 개인 측정값 → 밴드 라벨 결정적 해석엔진 (개인화 P1a, 경계선 ②).

설계 정본: docs/plan/14-personalization-consolidated.md §3·§6, 11-reference-band-seed-spec.md §4.

핵심 불변식 (이 모듈이 강제):
- [I1] 원시 측정값(120/80 등)을 반환하지 않는다. 밴드 식별자·라벨만 반환.
- [I12] 사용자 노출 라벨은 중립 3단(안정/주의/경고)만. 임상/질환 라벨(label, 예 "고혈압 1기")은
        내부 감사용으로만 동봉하고 표면화 책임은 호출측(personal_context)이 label_user만 사용.
- [결정성] LLM 비의존. 참조범위 시드(seed_reference_ranges._RANGES)의 bands를 규칙으로 평가.
- [fail-closed] 매칭 0/모호/축 결손/미구조화 → match != "ok", label_user=None (라벨 강제 생성 금지).
- [보수성] 한 측정이 여러 임상 카테고리에 걸리면(AND/OR·경계 겹침) 가장 보수적(경고>주의>안정) 라벨 채택.

lookup_band()은 순수 함수 — DB/네트워크/LLM 불필요. 단위테스트 가능.
다축(혈압 systolic/diastolic)은 value를 dict로 받는다. 단축 신호는 스칼라.
"""

from __future__ import annotations

from typing import Dict, Optional, Union

from seed_reference_ranges import _RANGES

# 사용자 노출 중립 라벨의 심각도 순서 (보수적 최댓값 채택용)
_SEVERITY = {"안정": 0, "주의": 1, "경고": 2}

Number = Union[int, float]


def _band_contains(band: Dict, v: Number) -> bool:
    """단일 밴드(min/max + 포함여부)가 값 v를 포함하는가. 단측 경계는 None."""
    lo = band.get("min")
    hi = band.get("max")
    if lo is not None:
        if v < lo:
            return False
        if v == lo and not band.get("min_inclusive", False):
            return False
    if hi is not None:
        if v > hi:
            return False
        if v == hi and not band.get("max_inclusive", False):
            return False
    return True


def _axis_value(value: Union[Number, Dict], axis: str) -> Optional[Number]:
    """다축 dict 또는 단축 스칼라에서 해당 축의 값을 꺼낸다. 없으면 None(fail-closed)."""
    if isinstance(value, dict):
        v = value.get(axis)
    else:
        # 스칼라는 단축 신호(axis 'value')로 취급
        v = value if axis == "value" else None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v


def _category_matches(category: Dict, value: Union[Number, Dict]) -> bool:
    """임상 카테고리(combine + bands)가 측정값에 매칭되는지 결정적 평가."""
    bands = category.get("bands") or []
    if not bands:
        return False
    combine = category.get("combine", "and")
    results = []
    for band in bands:
        axis = band.get("axis", "value")
        v = _axis_value(value, axis)
        if v is None:
            # 축 결손 → 이 밴드는 만족 불가 (fail-closed)
            results.append(False)
            continue
        results.append(_band_contains(band, v))
    if combine == "or":
        return any(results)
    # 기본 and: 모든 축 밴드 만족
    return all(results)


def lookup_band(
    signal_key: str,
    value: Union[Number, Dict],
    *,
    context: str = "clinic",
    locale: str = "KR",
    population: str = "adult",
) -> Dict:
    """측정값 → 밴드 결과(원시값 미반환).

    Args:
        signal_key: 'blood_pressure' 등 seed signal_key.
        value:      다축은 {'systolic':.., 'diastolic':..}, 단축은 스칼라.
        context:    'clinic'(기본) 등. 미구조화 context는 no_match(fail-closed).
        locale, population: 참조범위 엔트리 선택.

    Returns (원시 value·min·max 미포함):
        {signal_key, label_user('안정'|'주의'|'경고'|None), clinical_label(내부),
         match('ok'|'no_match'), context, locale, cite_doc_id, source_version}
    """
    base = {
        "signal_key": signal_key,
        "label_user": None,
        "clinical_label": None,   # 내부 감사용 — 표면화 금지(I12)
        "match": "no_match",
        "context": context,
        "locale": locale,
        "cite_doc_id": None,
        "source_version": None,
    }

    # 참조범위 엔트리 선택 (signal/locale/population 일치)
    entry = next(
        (
            r for r in _RANGES
            if r.get("signal_key") == signal_key
            and r.get("locale") == locale
            and r.get("population") == population
        ),
        None,
    )
    if entry is None:
        return base  # 미지원 신호/로케일 → fail-closed

    base["cite_doc_id"] = entry.get("id")
    base["source_version"] = entry.get("source_version")

    # context 일치하며 bands를 가진 카테고리만 평가 (미구조화 context는 자동 제외)
    candidates = [
        rng for rng in entry.get("ranges", [])
        if rng.get("bands") and rng.get("context", "clinic") == context
    ]
    if not candidates:
        return base  # 해당 context 미구조화 → fail-closed (예: home 아직 미구조화)

    matched = [c for c in candidates if _category_matches(c, value)]
    if not matched:
        return base  # 어떤 카테고리도 매칭 안 됨 → fail-closed

    # 보수적 최댓값: 가장 높은 심각도 라벨 채택 (경계 겹침·OR 중복 안전)
    worst = max(matched, key=lambda c: _SEVERITY.get(c.get("label_user", "안정"), 0))
    base["label_user"] = worst.get("label_user")
    base["clinical_label"] = worst.get("label")
    base["match"] = "ok"
    return base
