"""
personal_llm_context.py — 비식별 개인 맥락을 LLM 프롬프트에 주입 (방향 2).

원시 측정값·진단명·PII는 **절대 미투입**. 신호별 '중립 밴드 라벨'(안정/주의/경고)만 전달해
답변 본문을 사용자 상황에 맞춰 강조하게 한다(별도 후append 블록과 별개).

의료법·개인정보 통제를 코드로 강제(정본: docs/plan/17-personal-signal-to-llm-compliance.md):
  G1 기능 플래그 PERSONAL_SIGNAL_TO_LLM (기본 off → fail-closed, 미설정 시 행동 변화 0)
  G2 동의(consent) 없으면 미주입
  G3 응급 질의면 미주입(I7 — 응급 안내 우선)
  G4 국외이전 통제 — 국외(해외) LLM이면 ALLOW_CROSS_BORDER_PERSONAL ack 없이는 미주입
  G5 관련성 게이트 — 질의 관련 밴드만(과노출 차단, personal_context와 동일)
  G6 라벨-온리 백스톱 — 원시값/진단명이 섞이면 미주입(scan_personal_block)

build_llm_context()는 순수 함수(env·provider 속성만 읽음) — DB/LLM 불필요.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

# 국내(국외이전 아님)로 간주하는 provider type 기본값. env로 확장.
_DEFAULT_DOMESTIC = "self_hosted"

_SIGNAL_DISPLAY = {
    "blood_pressure": "혈압", "heart_rate": "심박수", "spo2": "산소포화도",
    "body_temperature": "체온", "bmi": "체질량지수", "air_quality": "실내 공기질",
}
_LABELS = {"안정", "주의", "경고"}


def _truthy(name: str) -> bool:
    return os.environ.get(name, "false").lower() in ("1", "true", "yes", "on")


def _domestic_providers() -> set:
    raw = os.environ.get("DOMESTIC_LLM_PROVIDERS", _DEFAULT_DOMESTIC)
    return {p.strip() for p in raw.split(",") if p.strip()}


def _provider_type(provider) -> Optional[str]:
    for attr in ("provider", "provider_type", "vendor"):
        v = getattr(provider, attr, None)
        if v:
            return str(v)
    return None


def _cross_border_ok(provider) -> bool:
    """[G4] 국내 provider면 OK. 국외/미상이면 명시 ack 있어야 허용(없으면 fail-closed)."""
    ptype = _provider_type(provider)
    if ptype and ptype in _domestic_providers():
        return True
    return _truthy("ALLOW_CROSS_BORDER_PERSONAL")


def candidate_items(findings, query) -> List[Tuple[str, str]]:
    """[G5] 관련성 게이트 통과 + 밴드 라벨(안정/주의/경고) 보유 finding → (표시명, 라벨).

    추세·환경(자체 sentence) finding은 LLM 맥락에 넣지 않는다(밴드 라벨만 — 최소·해석 안전).
    """
    from personal_context import relevance_gate
    out: List[Tuple[str, str]] = []
    for f in relevance_gate(query, findings or []):
        lab = f.get("label_user")
        if lab in _LABELS and not f.get("sentence"):
            out.append((_SIGNAL_DISPLAY.get(f.get("signal_key"), f.get("signal_key")), lab))
    return out


def render_context(items: List[Tuple[str, str]]) -> str:
    """비식별 밴드 라벨 목록 → 시스템 프롬프트용 맥락 문자열(원시값·진단명 0)."""
    if not items:
        return ""
    pairs = ", ".join(f"{d}={l}" for d, l in items)
    return (
        "[비식별 개인 맥락 — 참고용]\n"
        f"- 사용자의 최근 측정 구간(밴드): {pairs}\n"
        "지침: 위는 비식별 밴드 라벨이며 원시 수치·진단명이 아니다. 이를 반영해 일반 의학정보를 "
        "사용자 상황에 맞게 강조하되, 특정 질환으로 단정하거나 진단·처방하지 말 것. 수치를 추측·"
        "생성하지 말고, 항상 의료진 상담 안내를 포함할 것."
    )


def build_llm_context(findings, query, *, consent: bool = False,
                      provider=None, is_emergency: bool = False) -> str:
    """게이트 G1~G6을 모두 통과하면 LLM 프롬프트용 비식별 맥락 문자열, 아니면 ''(미주입)."""
    if is_emergency:                 # G3
        return ""
    if not _truthy("PERSONAL_SIGNAL_TO_LLM"):   # G1 (기본 off)
        return ""
    if not consent:                  # G2
        return ""
    if not _cross_border_ok(provider):          # G4
        return ""
    items = candidate_items(findings, query)    # G5
    if not items:
        return ""
    ctx = render_context(items)
    try:
        from personalization_safety import scan_personal_block
        if not scan_personal_block(ctx)["safe"]:   # G6 라벨-온리 백스톱
            return ""
    except Exception:
        return ""
    return ctx


def preview_context(findings, query) -> str:
    """플래그·provider 게이트와 무관하게 '주입될 내용'만 미리보기(관련성+라벨온리). UI/문서용."""
    return render_context(candidate_items(findings, query))


# ══════════════════════════════════════════════════════════════════
#  [데모] 전체 PHR 원시값 주입 — PERSONAL_RAW_TO_LLM (기본 off)
#  ⚠️ 방향2(밴드-온리, G6 라벨백스톱) 대비 **원시 수치·PHR을 그대로 LLM에 노출**한다.
#     합성 페르소나 데모 데이터 전용. 실 PHR 운영 전 반드시 재검토(정본 doc 17).
#     동의(G2)·응급(G3)·국외이전(G4) 게이트는 유지. 관련성/라벨백스톱은 미적용(원시=의도).
# ══════════════════════════════════════════════════════════════════
def _num(x) -> str:
    """정수형 float(152.0)는 152로, 소수(37.6)는 그대로 표기."""
    try:
        f = float(x)
        return str(int(f)) if f == int(f) else str(f)
    except Exception:
        return str(x)


def render_raw_context(personal) -> str:
    """파싱된 personal({vital_signs, phr, air_quality}) → 원시값 포함 LLM 맥락 문자열."""
    import json as _j
    lines: List[str] = []
    vitals = (personal or {}).get("vital_signs") or []
    if vitals:
        v = vitals[-1] or {}
        vs = []
        if v.get("bps") and v.get("bpd"):
            vs.append(f"혈압 {_num(v.get('bps'))}/{_num(v.get('bpd'))} mmHg")
        if v.get("bpm"):
            vs.append(f"심박수 {_num(v.get('bpm'))} bpm")
        if v.get("spo2"):
            vs.append(f"산소포화도 {_num(v.get('spo2'))}%")
        if v.get("fever"):
            vs.append(f"체온 {_num(v.get('fever'))}℃")
        if v.get("stress") is not None and v.get("stress") != "":
            vs.append(f"스트레스지수 {_num(v.get('stress'))}")
        if vs:
            lines.append("최근 측정값: " + ", ".join(vs))
    phr = (personal or {}).get("phr")
    if phr:
        try:
            p = _j.loads(phr) if isinstance(phr, str) else phr
        except Exception:
            p = None
        if isinstance(p, dict) and p:
            _kd = {"meds": "복약", "dx": "진단이력", "history": "병력", "checkup": "검진",
                   "hba1c": "당화혈색소", "bmi_band": "비만단계", "lifestyle": "생활습관",
                   "ldl": "LDL", "pregnancy": "임신", "breastfeeding": "수유", "status": "상태"}
            bits = []
            for k, val in p.items():
                if val in (None, "", [], {}):
                    continue
                label = _kd.get(k, k)
                v = ", ".join(map(str, val)) if isinstance(val, list) else str(val)
                bits.append(f"{label}: {v}")
            if bits:
                lines.append("건강기록(PHR): " + " · ".join(bits))
        elif p is None:
            lines.append("건강기록(PHR): " + str(phr))
    aq = (personal or {}).get("air_quality")
    if aq not in (None, ""):
        lines.append(f"실내 공기질 지수: {aq}")
    if not lines:
        return ""
    body = "\n".join("- " + l for l in lines)
    return (
        "[사용자 개인 건강 데이터 — 동의 하에 제공, 참고용]\n"
        f"{body}\n"
        "지침: 위는 사용자가 동의·제공한 개인 건강 데이터(원시 수치 포함)입니다. 이를 반영해 답변을 "
        "사용자 상황에 맞게 구체적으로 개인화하되, 확정 진단·처방은 하지 말고 필요 시 의료진 상담 안내를 포함하세요."
    )


def build_raw_context(personal, *, consent: bool = False,
                      provider=None, is_emergency: bool = False) -> str:
    """전체 PHR 원시값 주입 — PERSONAL_RAW_TO_LLM 플래그·동의·응급·국외이전 게이트 통과 시만."""
    if is_emergency:                              # G3
        return ""
    if not _truthy("PERSONAL_RAW_TO_LLM"):        # 기본 off — 안전 기본값 유지
        return ""
    if not consent:                               # G2
        return ""
    if not _cross_border_ok(provider):            # G4
        return ""
    return render_raw_context(personal)
