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


# ── 되묻기(clarify) — 어시스턴트가 묻고 사용자가 선택지로 답하는 형태 ──
# 각 질문에 options 제공 → 사용자가 고르면 그 정보로 다시 정밀 안내(멀티턴).
_CLARIFY_INTRO = "더 정확히 안내드리려면 아래를 알려주세요. 선택하시면 그 정보로 다시 안내드려요."
_CLARIFY_COMMON = [
    {"key": "duration", "q": "증상이 시작된 지 얼마나 됐나요?",
     "options": ["오늘", "2~3일", "일주일 이상", "한 달 이상"]},
    {"key": "severity", "q": "증상 정도는 어떤가요?", "options": ["가벼움", "보통", "심함"]},
]
_CLARIFY_TOPIC = {
    "bp": [
        {"key": "context", "q": "혈압은 어디서 재셨나요?", "options": ["가정", "병원", "약국", "모름"]},
        {"key": "accompany", "q": "함께 있는 증상은?", "options": ["두통", "어지럼", "가슴 통증", "없음"]},
        {"key": "meds", "q": "혈압약을 복용 중이신가요?", "options": ["복용 중", "아니오"]},
    ],
    "fever": [
        {"key": "temp", "q": "체온은 어느 정도인가요?", "options": ["미열(37~38)", "38~39", "39 이상", "모름"]},
        {"key": "accompany", "q": "동반 증상은?", "options": ["기침·인후통", "몸살", "설사·구토", "발진", "없음"]},
        {"key": "med", "q": "해열제를 드셨나요?", "options": ["먹어도 안 내림", "먹고 내림", "안 먹음"]},
    ],
    "resp": [
        {"key": "sputum", "q": "가래가 있나요?", "options": ["마른기침", "맑은 가래", "누런 가래", "피 섞임"]},
        {"key": "breath", "q": "숨참이 있나요?", "options": ["없음", "움직일 때", "가만히 있어도"]},
        {"key": "smoke", "q": "흡연하시나요?", "options": ["비흡연", "과거 흡연", "현재 흡연"]},
    ],
    "glucose": [
        {"key": "timing", "q": "언제 측정한 혈당인가요?", "options": ["공복", "식후 2시간", "무작위", "모름"]},
        {"key": "dx", "q": "당뇨 진단을 받으신 적 있나요?", "options": ["있음", "경계(전단계)", "없음"]},
        {"key": "meds", "q": "당뇨약을 복용 중이신가요?", "options": ["경구약", "인슐린", "없음"]},
    ],
    "headache": [
        {"key": "onset", "q": "통증이 어떻게 시작됐나요?", "options": ["서서히", "갑자기 심하게", "반복적으로"]},
        {"key": "redflag", "q": "다음 중 해당되는 것은?", "options": ["구토", "시야 이상", "팔다리 마비", "고열", "없음"]},
        {"key": "pattern", "q": "얼마나 자주 있나요?", "options": ["처음", "가끔", "자주(만성)"]},
    ],
    "chest": [
        {"key": "nature", "q": "가슴 통증은 어떤가요?", "options": ["쥐어짜는", "찌르는", "답답한", "타는 듯"]},
        {"key": "spread", "q": "통증이 퍼지나요?", "options": ["왼팔", "턱·목", "등", "아니오"]},
        {"key": "trigger", "q": "언제 심해지나요?", "options": ["움직일 때", "가만히 있어도", "숨 쉴 때"]},
    ],
}
_CLARIFY_GENERIC = [
    {"key": "accompany", "q": "함께 있는 증상이 있나요?", "options": ["발열", "두통", "어지럼", "통증", "없음"]},
    {"key": "history", "q": "해당되는 것이 있나요?",
     "options": ["복용 약 있음", "만성질환 있음", "임신·수유", "해당 없음"]},
]


def clarify(query: Optional[str], *, classification: Optional[dict] = None,
            personal_findings=None, max_q: int = 4) -> dict:
    """질의 → 되묻기 질문 목록(각 질문에 options). 사용자가 골라 멀티턴 정밀 안내로.

    Returns: {"intro": str, "questions": [{"key","q","options":[...]}, ...]}
    """
    q = query or ""
    domains = classification.get("medical_domains") if isinstance(classification, dict) else None
    topic_qs: List[dict] = []
    for topic, kws in _TOPIC_KW.items():
        if any(k in q for k in kws) or (domains and topic in domains):
            topic_qs += _CLARIFY_TOPIC.get(topic, [])
    if not topic_qs:
        topic_qs = _CLARIFY_GENERIC
    seen, out = set(), []
    for item in _CLARIFY_COMMON + topic_qs:
        if item["key"] in seen:
            continue
        seen.add(item["key"])
        out.append(item)
        if len(out) >= max_q:
            break
    return {"intro": _CLARIFY_INTRO, "questions": out}
