"""
followup_rewriter 단위 테스트 (06-multiturn-design.md §5/§6).

후속질의 판정·규칙 재작성의 정확도와 안전 불변식을 검증한다.
"""

from followup_rewriter import is_followup, rewrite_followup


# ── is_followup 판정 ──────────────────────────────────────────────────────────

def test_followup_detected_when_no_symptom_and_signal():
    """턴>0 + 증상매칭 0건 + 후속 신호 → 후속질의."""
    assert is_followup("언제 병원 가야 해요?", turn_count=1, current_symptom_keys=[])
    assert is_followup("약은 먹어도 되나요?", turn_count=2, current_symptom_keys=[])
    assert is_followup("얼마나 가나요?", turn_count=1, current_symptom_keys=[])


def test_not_followup_on_first_turn():
    """첫 턴(turn_count=0)은 후속이 아니다."""
    assert not is_followup("언제 병원 가야 해요?", turn_count=0, current_symptom_keys=[])


def test_not_followup_when_query_has_own_symptom():
    """질의 자체에 증상이 잡히면 독립 질의 — 후속 아님."""
    assert not is_followup("머리가 아파요", turn_count=1, current_symptom_keys=["headache"])


def test_not_followup_without_signal():
    """후속 신호가 없으면 후속 아님."""
    assert not is_followup("감사합니다", turn_count=1, current_symptom_keys=[])


# ── rewrite_followup 재작성 ──────────────────────────────────────────────────

def test_rewrite_when_to_visit():
    out, method = rewrite_followup("언제 병원 가야 해요?", "두통")
    assert method == "rule"
    assert "두통" in out and "진료" in out


def test_rewrite_which_department():
    out, method = rewrite_followup("무슨 과 가야 하나요?", "두통")
    assert method == "rule"
    assert "두통" in out and "과" in out


def test_rewrite_drug_question():
    out, method = rewrite_followup("약은 먹어도 되나요?", "두통")
    assert method == "rule"
    assert "두통" in out and "의약품" in out


def test_rewrite_duration_question():
    out, method = rewrite_followup("얼마나 가나요?", "두통")
    assert method == "rule"
    assert "두통" in out and "지속" in out


def test_rewrite_cause_question():
    out, method = rewrite_followup("왜 그런 거예요?", "두통")
    assert method == "rule"
    assert "두통" in out and "원인" in out


def test_rewrite_pronoun_substitution():
    out, method = rewrite_followup("그거 위험한가요?", "두통")
    assert method == "rule_pronoun"
    assert "두통" in out and "그거" not in out


def test_rewrite_miss_returns_original():
    """규칙·대명사 모두 미스 → 원본 유지, method='none'."""
    out, method = rewrite_followup("오늘 날씨 좋네요", "두통")
    assert method == "none"
    assert out == "오늘 날씨 좋네요"


def test_rewrite_without_last_symptom_returns_original():
    out, method = rewrite_followup("언제 병원 가야 해요?", "")
    assert method == "none"
    assert out == "언제 병원 가야 해요?"
