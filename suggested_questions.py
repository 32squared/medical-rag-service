"""suggested_questions.py — 사용자 프로필(관심 주제·기저질환) → 상세 질문 추천 (결정적, 순수).

목적: '상세 질문을 위한 사용자 정보 수집' — 수집한 프로필로 사용자가 물어볼 만한 구체 질문을
제안해 정보 탐색을 돕는다. 출력은 **질문(정보 탐색)뿐** — 의료 주장/진단/처방을 담지 않는다
(답변 자체는 RAG의 안전 가드레일이 처리). 민감 기저질환은 호출 측에서 동의 확인 후에만 전달.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 관심 주제 → 일반 정보 탐색 질문(주장 아님). 조건문("~할 때")으로 진단 함의 회피.
_TOPIC_Q = {
    "혈압": ["혈압 관리에 도움이 되는 식사가 궁금해요", "나트륨을 줄이는 실천 방법은 무엇이 있나요?"],
    "혈당": ["혈당 관리에 좋은 식습관이 궁금해요", "식후 활동이 혈당에 어떤 영향이 있나요?"],
    "콜레스테롤": ["콜레스테롤 관리에 도움이 되는 식사 방법이 궁금해요"],
    "체중": ["건강하게 체중을 관리하는 식단이 궁금해요"],
    "수면": ["수면의 질을 높이는 생활습관이 궁금해요"],
    "운동": ["초보자가 시작하기 좋은 운동이 궁금해요"],
    "식단": ["균형 잡힌 하루 식단 예시가 궁금해요"],
    "스트레스": ["스트레스를 줄이는 생활습관이 궁금해요"],
}
# 기저질환(동의 시) → 그 맥락의 일반 관리 정보 질문
_COND_Q = {
    "고혈압": ["고혈압이 있을 때 저염식은 어떻게 실천하나요?"],
    "당뇨": ["당뇨가 있을 때 탄수화물 섭취는 어떻게 조절하나요?"],
    "고지혈증": ["고지혈증이 있을 때 도움이 되는 식사가 궁금해요"],
    "비만": ["체중 관리를 위한 식사·활동 균형이 궁금해요"],
}

_FALLBACK = "요즘 건강에서 가장 궁금한 점은 무엇인가요?"


def suggest(topics: Optional[List[str]] = None,
            conditions: Optional[List[str]] = None, limit: int = 5) -> List[str]:
    """관심 주제·(동의된)기저질환 → 중복 제거·상한된 추천 질문. 비면 일반 폴백 1개."""
    out: List[str] = []
    seen = set()
    for src, table in ((conditions or [], _COND_Q), (topics or [], _TOPIC_Q)):
        for k in src:
            for q in table.get(k, []):
                if q not in seen:
                    seen.add(q)
                    out.append(q)
    return out[:limit] if out else [_FALLBACK]


def profile_summary(profile: Dict) -> str:
    """프로필 → 짧은 비식별 요약 문자열(표시·맥락용). 빈 값 생략."""
    parts = []
    if profile.get("age_band"):
        parts.append(str(profile["age_band"]))
    if profile.get("sex") and profile["sex"] != "선택안함":
        parts.append(str(profile["sex"]))
    if profile.get("topics"):
        parts.append("관심: " + ", ".join(profile["topics"][:4]))
    return " · ".join(parts)
