"""
증상 매처 부사삽입 내성 (reach — 부사가 표면형을 깨던 미탐지 수선).

"머리가 계속 아파요"처럼 정도·빈도 부사가 증상 표면형 사이에 끼면
substring 매칭이 깨져 미탐지되던 문제를 필러 제거로 해소했는지 검증한다.
"""

from symptom_matcher import match_symptoms, reload_matcher


def setup_module(module):
    reload_matcher()


# (입력, 기대 symptom_key)
_FILLER_CASES = [
    ("머리가 계속 아파요", "headache"),
    ("자꾸 머리가 아파요", "headache"),
    ("너무 배가 아파요", "abdominal_pain"),
    ("요즘 계속 기침이 나요", "cough"),
    ("조금 어지러워요", "dizziness"),
    ("심하게 토했어요", "vomiting"),
]


def test_filler_interleaved_still_matches():
    misses = []
    for text, key in _FILLER_CASES:
        keys = match_symptoms(text)
        if key not in keys:
            misses.append((text, keys))
    assert not misses, f"부사삽입 미탐지: {misses}"


def test_existing_surface_forms_still_match():
    """필러 제거가 기존 매칭을 깨지 않아야 한다(회귀 가드)."""
    assert "headache" in match_symptoms("머리아파")
    assert "headache" in match_symptoms("두통이 있어요")
    assert "abdominal_pain" in match_symptoms("배가 아파요")


def test_filler_strip_does_not_corrupt_words():
    """짧은 필러 제거로 증상어 부분문자열이 깨지지 않아야 한다.

    '막'을 필러로 제거하면 '결막염'→'결염'으로 파손되므로 제외했음을 회귀로 보장.
    '결막' 포함어가 다른 증상으로 *오매칭*되지 않으면 통과.
    """
    keys = match_symptoms("결막염 같아요")
    assert "headache" not in keys and "abdominal_pain" not in keys


def test_non_symptom_filler_returns_empty():
    assert match_symptoms("요즘 그냥 날씨가 좋네요") == []
