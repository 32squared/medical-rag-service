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

# [I8] 임상 판독 자체가 금지된 신호 (워치 ECG 등) — 밴드 조회 자체를 안 함.
DENY_SIGNALS = {"ecg", "ecg_waveform", "afib_alert"}

Number = Union[int, float]


def _select_entry(signal_key: str, locale: str, population: str) -> Optional[Dict]:
    """signal/locale/population 최적 참조범위 엔트리 선택.
    로케일은 정확>GLOBAL, 인구는 정확>all 폴백. 둘 다 미충족이면 None(fail-closed)."""
    cands = [r for r in _RANGES if r.get("signal_key") == signal_key]
    if not cands:
        return None

    def score(r: Dict):
        loc, pop = r.get("locale"), r.get("population")
        loc_s = 2 if loc == locale else (1 if loc == "GLOBAL" else 0)
        pop_s = 2 if pop == population else (1 if pop == "all" else 0)
        return (loc_s, pop_s)

    best = max(cands, key=score)
    loc_s, pop_s = score(best)
    if loc_s == 0 or pop_s == 0:
        return None  # 요청 로케일/인구에 적용 가능한 기준 없음
    return best


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
    device_grade: str = "clinical_near",
) -> Dict:
    """측정값 → 밴드 결과(원시값 미반환).

    Args:
        signal_key: 'blood_pressure' 등 seed signal_key.
        value:      다축은 {'systolic':.., 'diastolic':..}, 단축은 스칼라.
        context:    'clinic'(기본)/'home' 등. 미구조화 context는 no_match(fail-closed).
        locale, population: 참조범위 엔트리 선택(GLOBAL/all 폴백).
        device_grade: 'clinical_near'(기본)/'consumer'/'wellness'. 'wellness'는 임상밴드 비활성(I8).

    Returns (원시 value·min·max 미포함):
        {signal_key, label_user('안정'|'주의'|'경고'|None), clinical_label(내부),
         match('ok'|'no_match'|'denied'), context, locale, cite_doc_id, source_version}
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

    # [I8] deny 게이트 — 임상 판독 금지 신호 또는 웰니스 등급은 임상밴드 조회 자체를 안 함.
    if signal_key in DENY_SIGNALS or device_grade == "wellness":
        base["match"] = "denied"
        return base

    # 참조범위 엔트리 선택 (signal/locale/population, GLOBAL·all 폴백)
    entry = _select_entry(signal_key, locale, population)
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


# ── 추세 라벨 (정본 14 §6.2 — 중립 데이터 패턴만) ────────────────
# "점진개선/점진악화"는 건강 판단을 함의 → 의도적 제외(I2 정신, deny-list 동형).
# 추세 엔진은 데이터 형태만 기술하고, 호의(좋은 방향) 판단은 하지 않는다.
TREND_STABLE = "안정유지"
TREND_RISING = "지속상승"
TREND_FALLING = "지속저하"
TREND_FLUCTUATING = "불안정반복"


def label_trend(values, *, min_n: int = 3, rel_threshold: float = 0.05,
                noise_threshold: float = 0.03) -> Dict:
    """시간순 스칼라 시계열 → 중립 추세 라벨 (원시값 미반환, 결정적).

    Args:
        values: 시간 오름차순 측정값 리스트(스칼라). 비수치는 무시.
        min_n:  추세 판단 최소 표본(미만 → insufficient — 단일·소수 측정 추세 금지, 09 §6.2).
        rel_threshold:   순변화/평균 비율이 이 이상이면 상승/저하 추세.
        noise_threshold: 전체 변동폭/평균이 이 미만이면 안정유지(노이즈).

    Returns (원시값 미포함): {trend(라벨|None), match('ok'|'insufficient'), n}
    """
    nums = [v for v in (values or []) if _is_number(v)]
    n = len(nums)
    if n < min_n:
        return {"trend": None, "match": "insufficient", "n": n}

    mean = sum(nums) / n
    scale = max(abs(mean), 1e-9)
    rel_range = (max(nums) - min(nums)) / scale
    rel_net = (nums[-1] - nums[0]) / scale

    if rel_range < noise_threshold:
        return {"trend": TREND_STABLE, "match": "ok", "n": n}      # 전체가 노이즈 범위
    if rel_net >= rel_threshold:
        return {"trend": TREND_RISING, "match": "ok", "n": n}
    if rel_net <= -rel_threshold:
        return {"trend": TREND_FALLING, "match": "ok", "n": n}
    return {"trend": TREND_FLUCTUATING, "match": "ok", "n": n}     # 변동폭 크나 순변화 작음


# ── 교차신호 화이트리스트 (정본 14 §6 C9 / I9) ──────────────────
# 출처 첨부된 조합만 발화. 여기 없는 조합은 엔진이 생성 자체를 못 함(fail-closed).
# 비평가 경고(유사과학 교차: HRV+수면="번아웃")를 구조로 차단 — wellness_only는 영구 미발화.
# cite_doc_id는 동반적재용 forward-ref(KB 시드는 후속 — band finding과 동일 정책).
_CROSS_WHITELIST = [
    {
        "combo_id": "metabolic.bp_bmi",
        "signals": ["blood_pressure", "bmi"],
        "min_label": "주의",   # 둘 다 주의 이상일 때만
        "finding_template": "혈압과 체질량지수를 함께 살펴보면 좋은 시점입니다",
        "cite_doc_id": "ref.metabolic.kr",   # 비만-고혈압 연관(공인) — KB 시드 후속
        "wellness_only": False,
    },
    {
        # 웰니스 지표 단독 조합 — I9상 영구 미발화(예시·테스트용 가드).
        "combo_id": "wellness.hrv_sleep",
        "signals": ["hrv", "sleep_efficiency"],
        "min_label": "주의",
        "finding_template": "(미발화)",
        "cite_doc_id": None,
        "wellness_only": True,
    },
]


def match_cross_signals(findings) -> list:
    """활성 findings → 화이트리스트 조합 findings (I9, 결정적·fail-closed).

    화이트리스트에 등재된 조합만, 구성 신호가 모두 존재하고 모두 min_label 이상일 때 발화.
    wellness_only 조합은 영구 미발화(유사과학 교차 차단). 원시값 미포함.
    """
    by_sig = {f["signal_key"]: f for f in (findings or [])
              if f.get("label_user") in _SEVERITY}
    out = []
    for combo in _CROSS_WHITELIST:
        if combo.get("wellness_only"):
            continue  # I9: 웰니스 단독 교차 금지
        sigs = combo["signals"]
        if not all(s in by_sig for s in sigs):
            continue
        floor = _SEVERITY.get(combo["min_label"], 0)
        if all(_SEVERITY.get(by_sig[s]["label_user"], 0) >= floor for s in sigs):
            out.append({
                "combo_id": combo["combo_id"],
                "signals": list(sigs),
                "text": combo["finding_template"],
                "cite_doc_id": combo["cite_doc_id"],
                "type": "cross_signal",
            })
    return out


# vital_input.py 필드명 → 참조범위 signal_key (단축 신호).
# bps/bpd → blood_pressure(다축, 별도 처리), stress → 공인 밴드 없음(스킵).
_VITAL_FIELD_SIGNAL = {
    "bpm": "heart_rate",
    "spo2": "spo2",
    "fever": "body_temperature",
}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def run(
    record: Dict,
    *,
    locale: str = "KR",
    population: str = "adult",
    context: str = "clinic",
    device_grade: str = "clinical_near",
) -> list:
    """vital_input 레코드(단일) → findings 리스트 (정본 14 §6 C15, 경계선 ②→③ 브리지).

    `vital_input.parse_vital_signs`가 검증한 레코드({bpm,spo2,bps,bpd,fever,stress,...})를
    lookup_band로 해석해 findings(밴드 라벨·인용, **원시값 미포함**)로 변환한다.
    match=='ok'인 finding만 반환 — no_match/denied는 표면화하지 않음(fail-closed).
    findings는 personal_context(C19)가 렌더해 generate_response에 주입할 재료다.

    device_grade='wellness'(워치)면 lookup이 전부 denied → findings 0(임상밴드 비활성, I8).
    혈압은 bps·bpd 둘 다 있을 때만. stress는 공인 밴드 없어 스킵.
    """
    if not isinstance(record, dict):
        return []
    findings = []

    bps, bpd = record.get("bps"), record.get("bpd")
    if _is_number(bps) and _is_number(bpd):
        b = lookup_band(
            "blood_pressure", {"systolic": bps, "diastolic": bpd},
            locale=locale, population=population, context=context, device_grade=device_grade,
        )
        if b["match"] == "ok":
            findings.append(b)

    for field, signal in _VITAL_FIELD_SIGNAL.items():
        v = record.get(field)
        if _is_number(v):
            b = lookup_band(
                signal, v,
                locale=locale, population=population, context=context, device_grade=device_grade,
            )
            if b["match"] == "ok":
                findings.append(b)

    return findings


# ── 추세 finding (정본 14 §6.2 — 시계열 → 중립 추세 노트) ─────────
# bps→혈압(수축기 추세), spo2/fever/bpm도 단축 추세. stress는 공인 밴드 없어 제외.
_TREND_FIELDS = {"bps": "blood_pressure", "spo2": "spo2",
                 "fever": "body_temperature", "bpm": "heart_rate"}
_TREND_DISPLAY = {"blood_pressure": "혈압", "spo2": "산소포화도",
                  "body_temperature": "체온", "heart_rate": "심박수"}
# 안정유지는 미발화(노이즈 억제). 상승/저하/불안정만 데이터 패턴으로 기술(건강판단 없음).
_TREND_SENTENCE = {
    TREND_RISING: "최근 여러 차례 측정에서 {d}이(가) 점차 높아지는 흐름입니다",
    TREND_FALLING: "최근 여러 차례 측정에서 {d}이(가) 점차 낮아지는 흐름입니다",
    TREND_FLUCTUATING: "최근 {d} 측정값의 변동이 큰 편입니다",
}


def run_trends(records, *, min_n: int = 3) -> list:
    """시간순 vital 레코드들 → 신호별 중립 추세 finding (원시값 미포함, 결정적).

    각 신호 시계열에 label_trend를 적용해 '지속상승/지속저하/불안정반복'만 finding으로
    낸다(안정유지·표본부족은 미발화). 데이터 패턴만 기술하고 호의/악화 판단은 하지 않는다.
    personal_context가 finding의 sentence를 그대로 렌더(밴드 라벨과 동형 표면화).
    """
    if not isinstance(records, list) or len(records) < min_n:
        return []
    out = []
    for field, sig in _TREND_FIELDS.items():
        series = [r.get(field) for r in records
                  if isinstance(r, dict) and _is_number(r.get(field))]
        if len(series) < min_n:
            continue
        res = label_trend(series, min_n=min_n)
        if res["match"] != "ok":
            continue
        tmpl = _TREND_SENTENCE.get(res["trend"])
        if not tmpl:  # 안정유지 → 미발화
            continue
        out.append({
            "signal_key": sig, "label_user": None, "clinical_label": None,
            "match": "ok", "cite_doc_id": None, "source_version": None,
            "kind": "trend", "trend": res["trend"],
            "sentence": tmpl.format(d=_TREND_DISPLAY.get(sig, sig)),
        })
    return out
