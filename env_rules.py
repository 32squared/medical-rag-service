"""
env_rules.py — 실내 공기질 → 비해석적 환경 노트 (개인화 5층 환경×건강, 경계선 ②).

정본: docs/plan/14-personalization-consolidated.md(🔸 air_quality 환경 교차), 13 §환경,
      build_layer45_deepdive(5층 — '환경 영향 가능 + 환기 권유'가 천장).

규율(B5):
- [진단 아님] 공기질을 증상의 확정 원인으로 단정하지 않는다. '좋지 않은 수준 + 환기 권유'가 천장.
- [실내 한정] 실내 공기질만 다룬다(실외 혼동 금지).
- [중립 라벨] vital findings와 동형 라벨(주의/경고)을 써서 personal_context 관련성 게이트·렌더를
  그대로 재사용한다. finding은 자체 sentence(비인과적 환기 권유)를 동봉한다.
- [fail-closed] 보통/좋음/미상 → None(노트 미발화). 원시 수치 미노출.

air_quality_finding()은 순수 함수 — DB/LLM 불필요.
"""

from __future__ import annotations

from typing import Dict, Optional

# 한국 통합대기환경지수(CAI) 구간: 0~50 좋음, 51~100 보통, 101~250 나쁨, 251~ 매우나쁨
_LABEL_ALIASES = {
    "매우나쁨": "경고", "매우 나쁨": "경고", "very_bad": "경고", "very bad": "경고",
    "나쁨": "주의", "bad": "주의",
    "보통": None, "좋음": None, "good": None, "moderate": None, "normal": None,
}


def _grade(value) -> Optional[str]:
    """공기질 값(라벨 문자열 또는 CAI 수치) → 중립 라벨(주의/경고) 또는 None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # 수치(CAI)면 구간 매핑
    try:
        n = float(s)
        if n > 250:
            return "경고"
        if n > 100:
            return "주의"
        return None
    except ValueError:
        pass
    return _LABEL_ALIASES.get(s, None)


def air_quality_finding(value) -> Optional[Dict]:
    """공기질 값 → 환경 finding(비인과·환기 권유) 또는 None.

    Returns (원시값 미포함, personal_context가 그대로 렌더):
        {signal_key:'air_quality', label_user:'주의'|'경고', clinical_label:None,
         match:'ok', kind:'environment', cite_doc_id:'ref.env.kr', sentence:str}
    보통/좋음/미상 → None(노트 미발화, fail-closed).
    """
    label = _grade(value)
    if not label:
        return None
    strength = "환기와 장시간 실내 노출 줄이기를 권장합니다" if label == "경고" else "환기를 권장합니다"
    sentence = (
        f"최근 실내 공기질이 좋지 않은 수준으로 확인되어, {strength}"
        " (증상의 원인 단정은 아니며, 증상이 지속되면 진료를 권합니다)"
    )
    return {
        "signal_key": "air_quality",
        "label_user": label,
        "clinical_label": None,
        "match": "ok",
        "cite_doc_id": "ref.env.kr",  # 환경-호흡기 환기 권유(공인) — KB 시드 후속
        "source_version": None,
        "kind": "environment",
        "sentence": sentence,
    }
