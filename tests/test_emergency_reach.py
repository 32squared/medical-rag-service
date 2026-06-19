"""
응급/위기 구어체 도달 골든셋 (reach §9.4 안전 급소).

규칙 기반 분류기가 *구어체·띄어쓰기 변형*의 응급/위기 신호를 놓치지 않는지 검증한다.
의료 안전상 가장 치명적인 미탐지(놓친 응급)를 회귀로 막는 게이트.

원칙(00 P2): 보수(위험) 방향으로 분류 — 모호하면 응급/위기로.
단, 거짓양성(과대 트리아지)도 별도 가드 케이스로 측정한다(레드팀 #4).
"""

from medical_classifier import classify_rule_based


# (입력, 기대 intent, 기대 red_flag 부분집합)
_EMERGENCY_COLLOQUIAL = [
    ("숨을 못 쉬겠어요", "emergency", "dyspnea"),
    ("갑자기 숨을 쉴 수 없어요", "emergency", "dyspnea"),
    ("숨이 턱 막혀요", "emergency", "dyspnea"),
    ("계속 헐떡거려요", "emergency", "dyspnea"),
    ("가슴이 조여와요", "emergency", "chest_pain"),
    ("가슴을 쥐어짜는 것 같아요", "emergency", "chest_pain"),
    ("가슴이 터질 것 같아요", "emergency", "chest_pain"),
    ("정신을 잃을 것 같아요", "emergency", "loss_of_consciousness"),
    ("자꾸 까무러쳐요", "emergency", "loss_of_consciousness"),
    ("피를 토했어요", "emergency", "severe_bleeding"),
    ("피가 안 멈춰요", "emergency", "severe_bleeding"),
    ("온몸이 뻣뻣해지면서 거품을 물어요", "emergency", "seizure"),
    ("말이 꼬여요", "emergency", "stroke_symptoms"),
    ("혀가 꼬여서 발음이 안 돼요", "emergency", "stroke_symptoms"),
]

_CRISIS_COLLOQUIAL = [
    "죽고싶어요",
    "그냥 다 죽어버리고 싶어요",
    "이제 살기 싫어요",
    "목숨을 끊고 싶다는 생각이 들어요",
    "살아서 뭐 하나 싶어요",
]

# 거짓양성 가드 — 응급이 아니어야 하는 일상/경증 표현
_NON_EMERGENCY = [
    ("요즘 너무 피곤해요", "emergency"),
    ("가슴이 두근거려요", "emergency"),
    ("머리가 좀 아파요", "emergency"),
]


def test_emergency_colloquial_detected():
    misses = []
    for text, intent, flag in _EMERGENCY_COLLOQUIAL:
        r = classify_rule_based(text)
        if r["intent"] != intent or flag not in r["red_flags"]:
            misses.append((text, r["intent"], r["red_flags"]))
    assert not misses, f"미탐지 응급 구어체: {misses}"


def test_emergency_sets_emergency_guidance_mode():
    for text, _, _ in _EMERGENCY_COLLOQUIAL:
        r = classify_rule_based(text)
        assert r["allowed_response_mode"] == "emergency_guidance", text
        assert r["risk_level"] == "very_high", text


def test_crisis_colloquial_detected():
    misses = []
    for text in _CRISIS_COLLOQUIAL:
        r = classify_rule_based(text)
        if r["intent"] != "mental_health_crisis":
            misses.append((text, r["intent"]))
    assert not misses, f"미탐지 위기 구어체: {misses}"


def test_crisis_sets_crisis_guidance_mode():
    for text in _CRISIS_COLLOQUIAL:
        r = classify_rule_based(text)
        assert r["allowed_response_mode"] == "crisis_guidance", text
        assert "suicidal_ideation" in r["red_flags"], text


def test_no_false_positive_emergency():
    """일상·경증 표현이 응급으로 오분류되지 않아야 한다(과대 트리아지 가드)."""
    fp = []
    for text, bad_intent in _NON_EMERGENCY:
        r = classify_rule_based(text)
        if r["intent"] == bad_intent:
            fp.append((text, r["intent"]))
    assert not fp, f"거짓양성 응급: {fp}"
