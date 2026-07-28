"""
personalization_safety.py — 개인화 출력 안전 게이트 (배선 선결, 정본 14 §6·§7).

두 미구현 선결 게이트(아키텍트·비평가 지목)를 순수 함수로 구현:
- [C21 / I2] find_clinical_labels — 명사구 진단·병기 라벨 탐지.
    citation_verifier.py 의 종결어미 정규식(`...입니다`)이 놓치는
    "고혈압 1기", "당뇨병 기준에 해당하는 수치가 확인됩니다", "N단계 비만" 류를 잡는다.
- [C20 / I1·V1] scan_personal_block — 개인 기록 블록 출고 전 백스톱.
    원시값(2자리+ 숫자)·질환명·임상 병기 라벨이 0인지 검증(라벨만이어야 함).

설계상 personal_context.build()의 출력은 이미 안전(라벨만)하나, 이 게이트는
generate_response 주입 직전(stream_chat 전)의 **런타임 백스톱**이다 — 향후 PHR/OCR
경로(자유텍스트 V1)가 배선될 때 단일 코드 실수로도 원시값·진단명이 안 새도록 잠근다.

전부 순수 함수 — DB/LLM 불필요.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# [C21] 시드 임상/병기 라벨 — 사용자 출력에 등장하면 개인귀속 진단(I2). 공백 변형 허용.
_CLINICAL_LABEL_RE = re.compile(
    r"(고혈압\s*\d\s*기"
    r"|고혈압\s*전단계"
    r"|당뇨병\s*기준"
    r"|당뇨병\s*전단계"
    r"|공복혈당장애"
    r"|\d\s*단계\s*비만"
    r"|비만\s*전단계"
    r"|중증\s*저산소혈증)"
)

# 개인 기록 블록에 등장하면 안 되는 질환명 (블록은 중립 라벨 '안정/주의/경고' 문구만이어야 함).
# 측정명(혈압·혈당)은 질환명이 아니므로 제외 — 질환형(고혈압·당뇨병)만.
_DISEASE_NOUNS = (
    "고혈압", "저혈압", "당뇨병", "당뇨", "비만", "저산소혈증",
    "만성콩팥병", "신부전", "골다공증", "골감소증", "이상지질혈증", "고지혈증", "빈혈",
)

# 원시 측정값 백스톱 — 2자리 이상 숫자(120·80·98·165…). 블록은 라벨만이라 숫자 0이어야 함.
_MULTI_DIGIT_RE = re.compile(r"\d{2,}")

# [C22] 거짓안심 절대표현 — 측정 기반 단정적 안심은 위험(거짓안심 0 = 1급 KPI).
# 개인화 블록에 등장하면 주입 차단. ('특이소견이 보이지 않습니다'처럼 측정시점으로 한정·완화된
# 안정 문구는 여기 없음 — 단정적·무조건적 안심만 금지.)
_FALSE_REASSURE = (
    "위급하지 않", "걱정하지 않아도", "걱정 안 해도", "걱정마", "걱정 마",
    "안심하셔도", "안심하세요", "정상입니다", "이상 없습니다", "이상이 없습니다",
    "문제없습니다", "문제 없습니다", "괜찮습니다", "괜찮아요",
)


def find_clinical_labels(text: Optional[str]) -> List[str]:
    """[C21] 명사구 진단·병기 라벨 탐지. 발견 목록 반환(없으면 빈 리스트)."""
    if not text:
        return []
    return _CLINICAL_LABEL_RE.findall(text)


def find_false_reassurance(text: Optional[str]) -> List[str]:
    """[C22] 거짓안심 절대표현 탐지. 발견 목록 반환(없으면 빈 리스트)."""
    if not text:
        return []
    return [p for p in _FALSE_REASSURE if p in text]


def scan_personal_block(text: Optional[str]) -> Dict:
    """[C20] 개인 기록 블록 백스톱. 원시값·질환명·임상라벨 0 검증.

    Returns: {"safe": bool, "violations": [str, ...]}
    """
    violations: List[str] = []
    if not text:
        return {"safe": True, "violations": []}
    if _MULTI_DIGIT_RE.search(text):
        violations.append("raw_value")
    for noun in _DISEASE_NOUNS:
        if noun in text:
            violations.append(f"disease_noun:{noun}")
    for lbl in find_clinical_labels(text):
        violations.append(f"clinical_label:{lbl}")
    for phr in find_false_reassurance(text):
        violations.append(f"false_reassurance:{phr}")
    return {"safe": not violations, "violations": violations}


def assert_personal_block_safe(text: Optional[str]) -> None:
    """주입 직전 호출용 — 위반 시 ValueError(fail-closed). 호출측은 개인화 블록을 드롭한다."""
    result = scan_personal_block(text)
    if not result["safe"]:
        raise ValueError(
            f"개인화 블록 안전 위반(주입 차단): {', '.join(result['violations'])}"
        )
