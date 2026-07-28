"""test_suggested_questions.py — 프로필→상세 질문 추천(순수). 주장 없음·동의 분리·중복/상한."""
import suggested_questions as sq


def test_topic_questions():
    qs = sq.suggest(topics=["혈압"])
    assert qs and any("혈압" in q for q in qs)
    assert all(q.endswith("?") or "궁금" in q for q in qs)   # 질문 형태(주장 아님)


def test_conditions_prioritized_and_deduped():
    qs = sq.suggest(topics=["혈압"], conditions=["고혈압"])
    assert qs[0].startswith("고혈압이 있을 때")            # 기저질환 우선
    assert len(qs) == len(set(qs))                          # 중복 없음


def test_limit_cap():
    qs = sq.suggest(topics=["혈압", "혈당", "체중", "수면", "운동", "식단"], limit=3)
    assert len(qs) == 3


def test_empty_fallback():
    assert sq.suggest() == [sq._FALLBACK]
    assert sq.suggest(topics=[], conditions=[]) == [sq._FALLBACK]


def test_no_medical_claims_in_questions():
    # 추천은 정보 탐색 질문일 뿐 — 효능/단정 표현 없어야
    banned = ["완치", "낫는다", "치료됩니다", "효과가 있다", "보장"]
    allq = []
    for t in sq._TOPIC_Q:
        allq += sq.suggest(topics=[t])
    for c in sq._COND_Q:
        allq += sq.suggest(conditions=[c])
    for q in allq:
        assert not any(b in q for b in banned), q


def test_profile_summary_deidentified():
    s = sq.profile_summary({"age_band": "50대", "sex": "여", "topics": ["혈압", "체중"]})
    assert "50대" in s and "여" in s and "혈압" in s
    assert sq.profile_summary({"sex": "선택안함"}) == ""    # 선택안함·빈 값은 생략
