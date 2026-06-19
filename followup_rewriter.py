"""
Followup Rewriter — 후속질의 판정·재작성 (06-multiturn-design.md §5).

멀티턴 대화에서 "언제 병원 가야 해요?", "약은 먹어도 되나요?" 같은 후속질의는
그 자체로는 증상 매칭·검색이 안 되어 insufficient로 빠진다. 직전 주제
(last_symptom_name)를 주어로 복원해 독립(standalone) 검색 질의로 재작성한다.

설계 원칙:
- 규칙 우선(LLM 비용 0, 결정적). 모호하면 LLM 폴백(이 모듈 범위 밖, 호출자가 담당).
- 재작성은 **검색 질의에만** 적용(§6-2). 사용자 답변·면책·인용 정책은 단일 턴과 동일.
- 안전 불변식(§6-1): 원본 질의에 crisis/emergency 신호가 있으면 후속으로 보지 않고
  독립 질의로 처리한다 — 문맥이 안전 분기를 약화시키지 않도록.

순수 함수 — DB/LLM 없이 로컬 테스트 가능. is_followup의 증상 매칭 여부는
호출자가 매처를 돌려 current_symptom_keys로 주입한다(의존성 역전).
"""

from __future__ import annotations

import re
from typing import List, Tuple

# 후속 신호 → 재작성 템플릿 ({s} = last_symptom_name). 순서 = 우선순위.
_FOLLOWUP_RULES: List[Tuple["re.Pattern", str]] = [
    (re.compile(r"언제.*(병원|응급실|진료|가야|가요|가나요|가면)"), "{s}일 때 언제 진료가 필요한가요"),
    (re.compile(r"(무슨|어느|어떤)\s*과"), "{s}은 어느 과에서 진료하나요"),
    (re.compile(r"(약은|약을|약\s|먹어도|복용)"), "{s} 관련 일반의약품 정보"),
    (re.compile(r"(얼마나|며칠|기간)"), "{s} 증상 지속 기간"),
    (re.compile(r"(왜|원인|이유)"), "{s} 원인"),
]

# 대명사 치환 대상 (긴 것 우선 — "그게" 전에 "그것" 등)
_PRONOUNS = ["그것", "이것", "그거", "이거", "그게", "이게", "그건", "이건", "저거"]

# 후속질의로 의심되는 지시/생략 신호 (이게 있어야 후속 후보)
_FOLLOWUP_SIGNALS = re.compile(
    r"언제|얼마나|며칠|기간|무슨\s*과|어느\s*과|어떤\s*과|"
    r"약은|약을|먹어도|복용|왜|원인|이유|그것|이것|그거|이거|그게|이게|그건|이건"
)


def is_followup(query: str, turn_count: int, current_symptom_keys: List[str]) -> bool:
    """현재 질의가 직전 주제에 대한 후속질의인지 규칙 판정.

    조건(설계 §3-2): turn_count>0 + 현재 질의에서 증상 매칭 0건 + 후속 신호 존재.

    Args:
        query: 현재 사용자 질의(원본).
        turn_count: 직전까지의 대화 턴 수(0이면 첫 턴 → 후속 아님).
        current_symptom_keys: 현재 질의를 매처에 돌린 결과(있으면 독립 질의).
    """
    if turn_count <= 0:
        return False
    if current_symptom_keys:  # 자체로 증상이 잡히면 독립 질의 — 재작성 불필요
        return False
    q = (query or "").strip()
    if not q:
        return False
    return bool(_FOLLOWUP_SIGNALS.search(q))


def rewrite_followup(query: str, last_symptom_name: str) -> Tuple[str, str]:
    """후속질의를 직전 증상 기준 독립 질의로 재작성(규칙 우선).

    Returns:
        (rewritten_query, method) — method ∈ {"rule", "rule_pronoun", "none"}.
        규칙 미스 시 (원본, "none") → 호출자가 LLM 폴백을 결정.
    """
    if not last_symptom_name:
        return query, "none"
    q = (query or "").strip()
    if not q:
        return query, "none"

    for pat, tmpl in _FOLLOWUP_RULES:
        if pat.search(q):
            return tmpl.format(s=last_symptom_name), "rule"

    # 대명사 치환 (규칙 미스 시)
    for pron in _PRONOUNS:
        if pron in q:
            return q.replace(pron, last_symptom_name), "rule_pronoun"

    return query, "none"
