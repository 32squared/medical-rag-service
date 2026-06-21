"""
followups.py — 후속 질문 제안 (멀티턴 버튼용, 결정적).

질의·분류·개인화 맥락에서 사용자가 이어서 누를 만한 후속 질문 2~3개를 만든다.
뷰어는 이를 선택 버튼으로 렌더(클릭=다음 턴). RAG(generate_response)도 STOP에 동봉한다.

suggest()는 순수 함수 — DB/LLM 불필요. 질의 키워드(+선택적 분류 도메인) 기반.
"""

from __future__ import annotations

from typing import List, Optional

# 토픽 → 사용자 관점 후속 질문(다음 턴으로 보낼 자연스러운 질의)
_TOPIC_KW = {
    "bp": ["혈압", "고혈압", "저혈압", "수축기", "이완기"],
    "fever": ["열", "발열", "미열", "체온", "몸살", "오한", "고열"],
    "resp": ["기침", "가래", "숨", "호흡", "천식", "코로나", "독감", "인후통"],
    "glucose": ["혈당", "당뇨", "당화", "공복혈당"],
    "weight": ["체중", "비만", "살", "몸무게", "체질량"],
    "drug": ["약", "복용", "처방", "진통제", "감기약", "해열제"],
    "headache": ["두통", "편두통", "머리", "어지럼", "현기증"],
    "chest": ["가슴", "흉통", "심장", "두근"],
}
_TOPIC_Q = {
    "bp": ["혈압을 낮추는 생활습관을 알려주세요", "지금 바로 병원에 가야 하나요?",
           "가정에서 혈압을 정확히 재는 방법은?"],
    "fever": ["해열제는 어떻게 복용하나요?", "언제 응급실에 가야 하나요?",
              "감기와 독감은 어떻게 구분하나요?"],
    "resp": ["어느 진료과에 가야 하나요?", "기침이 오래가면 어떤 검사를 하나요?",
             "실내 환기는 어떻게 하면 좋나요?"],
    "glucose": ["혈당 관리 식단을 알려주세요", "당화혈색소는 무슨 의미인가요?",
                "운동은 어떻게 하면 좋나요?"],
    "weight": ["건강하게 체중 줄이는 방법은?", "비만은 어떤 위험이 있나요?",
               "어떤 운동이 도움이 되나요?"],
    "drug": ["임신·수유 중에도 괜찮은가요?", "다른 약과 함께 먹어도 되나요?",
             "흔한 부작용은 무엇인가요?"],
    "headache": ["위험한 두통은 어떻게 구분하나요?", "편두통은 어떻게 관리하나요?",
                 "어느 진료과에 가야 하나요?"],
    "chest": ["지금 응급실에 가야 하나요?", "어느 진료과에 가야 하나요?",
              "어떤 검사를 받게 되나요?"],
}
_GENERIC = ["어느 진료과에 가야 하나요?", "증상이 더 심해지면 어떻게 하나요?",
            "집에서 할 수 있는 관리법은?"]


def suggest(query: Optional[str], *, classification: Optional[dict] = None,
            personal_findings=None, max_n: int = 3) -> List[str]:
    """질의(+선택적 분류/개인화) → 후속 질문 제안 목록(중복 제거, 최대 max_n)."""
    q = query or ""
    domains = []
    if isinstance(classification, dict):
        domains = classification.get("medical_domains") or []
    out: List[str] = []
    for topic, kws in _TOPIC_KW.items():
        if any(k in q for k in kws) or topic in domains:
            for s in _TOPIC_Q[topic]:
                if s not in out:
                    out.append(s)
    # 토픽 매칭이 없으면 일반 후속 질문으로 채움(빈 버튼 방지)
    for s in _GENERIC:
        if len(out) >= max_n:
            break
        if s not in out:
            out.append(s)
    return out[:max_n]
