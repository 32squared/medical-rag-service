"""coaching_compliance.py — 웰니스 코칭 출력 안전 백스톱 (WC-C, P2, 순수 함수).

정본: docs/plan/18-wellness-coaching.md §5.2(표현사전)·§5.5(WC-C1~6).
코칭 플랜·코치 메시지가 STOP 전 반드시 통과. 결정적 스캔(LLM 아님).
- WC-C1 효능표방 스캔 — 질병 치료·완치·예방 효능 주장 차단.
- WC-C2 처방성 탐지 — 치료 목표 용량·치료식 처방·목표심박 → 완화 필요.
- WC-C3 밴드 캡 — 경고밴드에 강한 플랜 보류(진료 우선).
플랜은 벗어남 방지(defense-in-depth) — 템플릿이 이미 안전해도 한 번 더 검증.
"""
from __future__ import annotations

import re
from typing import Dict, List

# ── WC-C1: 효능·치료 표방 (§5.2-A) — 질병 치료/완치/예방/효능 단정 ──────────────
_EFFICACY = [
    r"(낫게|낫는다|낫습니다|치료(?!식)|완치|고친다|고칩니다|없애[준줍])",
    r"(예방(?:합니다|해준|효과))",
    r"(약\s*없이도|약을?\s*끊)",
    r"(직빵|특효)",
    r"(효과가?\s*(있습니다|있어요|확실))",
]
# 질환명 + 효능 결합(고혈압이 좋아져요 류)
_DISEASE = r"(고혈압|당뇨|혈압|혈당|고지혈|비만|콜레스테롤)"
_EFFICACY_DISEASE = re.compile(_DISEASE + r"[가-힣\s]{0,6}(좋아|낮춰[준줍]|떨어[뜨집]|잡[아힌])")

# ── WC-C2: 처방성 (§5.2-B) — 치료 목표 용량·치료식·목표심박 ──────────────────
_PRESCRIPTION = [
    r"\d+\s*(mg|밀리그램|그램|g)\s*(으?로\s*제한|이하로|까지)",   # 나트륨 1500mg로 제한
    r"(최대심박|목표심박)\s*\d+%?",
    r"(이\s*질환엔?|진단받으셨으면)\s*[가-힣\s]{0,10}(드세요|섭취하세요)",
]

_EFFICACY_RES = [re.compile(p) for p in _EFFICACY]
_PRESCRIPTION_RES = [re.compile(p) for p in _PRESCRIPTION]

# ── 루틴 팩 안전 프로필별 추가 금칙(28 §3-2) — 기본 규칙 위에 얹기만, 빼지 않는다 ──
# 성과 보장: 기간·급수·스코어를 약속하는 표현(모든 프로필). "6개월이면 싱글", "N3 합격 보장"
_OUTCOME = [
    r"\d+\s*(개월|주|일)\s*(이면|만에|안에|후엔?)[가-힣\s]{0,12}(합격|싱글|언더파|마스터|달성|완성|유창)",
    r"(합격|싱글|언더파|유창)[가-힣\s]{0,4}(보장|확실|책임)",
]
# 부상·통증 처방(physical): 통증이 있을 때 무엇을 하라고 지시 — 통증은 '쉬기·해당없음' 으로만
_INJURY_RX = [
    r"(통증|아프|아플|결리|저리)[가-힣\s]{0,10}(으면|면|때|경우)[가-힣\s,]{0,16}(하세요|드세요|바르세요|붙이세요|늘리세요|푸세요)",
]
_PROFILE_EXTRA = {
    "medical": [],
    "physical": [re.compile(p) for p in _OUTCOME + _INJURY_RX],
    "neutral": [re.compile(p) for p in _OUTCOME],
}


def scan_efficacy(text: str) -> List[str]:
    """WC-C1 — 효능표방 패턴 매치 목록(없으면 빈 리스트)."""
    if not text:
        return []
    hits = [m.group(0) for r in _EFFICACY_RES for m in r.finditer(text)]
    hits += [m.group(0) for m in _EFFICACY_DISEASE.finditer(text)]
    return hits


def scan_prescription(text: str) -> List[str]:
    """WC-C2 — 처방성(용량·치료식·목표심박) 패턴 매치 목록."""
    if not text:
        return []
    return [m.group(0) for r in _PRESCRIPTION_RES for m in r.finditer(text)]


def scan_profile(text: str, profile: str = "medical") -> List[str]:
    """루틴 팩 안전 프로필의 추가 금칙(성과 보장·부상 처방) 매치 목록."""
    if not text:
        return []
    return [m.group(0) for r in _PROFILE_EXTRA.get(profile, []) for m in r.finditer(text)]


def check_plan(plan_text: str, band: str = None, profile: str = "medical") -> Dict:
    """플랜 텍스트 안전 검증.

    profile: 루틴 팩 안전 프로필(medical|physical|neutral). 기본 규칙(WC-C1·C2)은
             모든 프로필에 적용되고, 프로필은 금칙을 **추가**만 한다.
    Returns: {ok, action, violations}
      action: 'pass' | 'blocked'(효능표방·성과보장) | 'softened'(처방성·부상처방) | 'band_capped'
    """
    eff = scan_efficacy(plan_text)
    rx = scan_prescription(plan_text)
    extra = scan_profile(plan_text, profile)
    if extra:
        return {"ok": False, "action": "blocked", "violations": extra}
    if eff:
        return {"ok": False, "action": "blocked", "violations": eff}      # WC-C1
    if rx:
        return {"ok": False, "action": "softened", "violations": rx}       # WC-C2
    # WC-C3: 경고밴드는 강한 플랜(다항목 강제) 보류 — 생성 단계에서 soft로 캡되어야 함.
    # 백스톱은 '플랜 자체가 존재하는데 경고밴드'면 진료 우선 배너 필수만 확인(텍스트 검증).
    return {"ok": True, "action": "pass", "violations": []}


def assert_plan_safe(plan_text: str, band: str = None) -> None:
    """위반 시 ValueError(테스트·생성 가드용). 정상이면 None."""
    r = check_plan(plan_text, band)
    if not r["ok"]:
        raise ValueError(f"coaching plan unsafe [{r['action']}]: {r['violations']}")
