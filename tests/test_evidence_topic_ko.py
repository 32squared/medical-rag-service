"""
evidence_topic 한국어 표시어 — 근거 게이트 주제 정렬.

영문 snake_case 라벨('fasting_glucose')은 한국어 질의와 임베딩 코사인이 0.1대라 게이트의
topic_match 문턱(0.30)을 거의 넘지 못했다. check_evidence_topic_alignment 는 비교할 때만
라벨을 한국어 표시어로 바꾼다(evidence_topic_ko.topic_phrase). DB 라벨은 그대로다.
"""
import os
import re
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag_engine  # noqa: E402
from evidence_topic_ko import topic_phrase  # noqa: E402
from rag_engine import check_evidence_topic_alignment, evaluate_retrieval_gate  # noqa: E402

_HANGUL = re.compile(r"[가-힣]")

# dev KB(medical_app_dev) 활성 청크의 영문 evidence_topic 전체 — 2026-09-29 조회(119종 중 한글 라벨 8종 제외)
DEV_KB_LABELS_2026_09_29 = [
    'abdominal_pain', 'acne', 'aed_usage', 'age_drug_safety', 'anxiety', 'back_pain',
    'blood_pressure', 'bloody_stool', 'bmi', 'body_pain', 'body_temperature', 'bp_abnormal',
    'cancer_general', 'cancer_screening', 'cardiac_arrest', 'chest_pain', 'chest_pain_resp',
    'child_emergency', 'chronic_cough', 'co2_indoor', 'constipation',
    'consultation_cardiovascular', 'consultation_dermatology', 'consultation_digestive',
    'consultation_ent', 'consultation_mental', 'consultation_musculoskeletal',
    'consultation_neuro', 'consultation_respiratory', 'consultation_systemic',
    'consultation_urogenital', 'cough', 'dementia', 'depression', 'diabetes', 'diabetes_care',
    'diagnosis', 'diarrhea', 'dizziness', 'drug_administration', 'drug_dosage', 'drug_duplication',
    'drug_duration', 'drug_interaction', 'dyspnea', 'dysuria', 'ear_pain', 'elderly_drug_safety',
    'elderly_fall', 'elderly_medication', 'emergency_dismiss', 'emergency_signs', 'eye_pain',
    'fasting_glucose', 'fatigue', 'fever', 'frequency', 'general', 'hba1c', 'headache',
    'heart_rate', 'heartburn', 'hematuria', 'hospital_referral', 'hypertension_care',
    'impersonation', 'insomnia', 'itching', 'knee_pain', 'leg_edema', 'legal_emergency',
    'legal_medical_advertising', 'legal_privacy', 'legal_unlicensed_practice', 'memory_loss',
    'menstrual', 'mental_health', 'metabolic', 'myalgia', 'nasal_congestion', 'navigation_checkup',
    'navigation_department', 'navigation_emergency', 'navigation_insurance',
    'navigation_visit_prep', 'numbness', 'palpitation', 'personalized_treatment', 'pm10', 'pm25',
    'poisoning', 'post_procedure_advice', 'pregnancy', 'pregnancy_drug_safety', 'prescription',
    'radiating_arm_pain', 'rare_disease', 'rash', 'respiratory_care', 'risk_probability',
    'seizure', 'shoulder_pain', 'skin_tumor', 'sleep', 'spo2', 'stress', 'test_procedure',
    'throat_pain', 'vaccination', 'vision_loss', 'weight_change',
]


class TestTopicPhrase:
    def test_symptom_key_uses_catalog_name(self):
        assert topic_phrase("fever") == "발열"
        assert topic_phrase("abdominal_pain") == "복통"
        assert topic_phrase("pediatric_fever") == "소아 발열"  # symptom_supplement 보강 키

    def test_seed_label_mapped(self):
        assert topic_phrase("fasting_glucose") == "공복혈당 기준"
        assert "진료과" in topic_phrase("navigation_department")

    def test_korean_label_unchanged(self):
        assert topic_phrase("공복혈당 당뇨병 검진 판정기준") == "공복혈당 당뇨병 검진 판정기준"

    def test_unknown_and_empty_unchanged(self):
        assert topic_phrase("fever_pediatric") == "fever_pediatric"
        assert topic_phrase("") == ""
        assert topic_phrase(None) is None

    def test_general_label_unchanged(self):
        """주제 정보가 없는 수집기 기본 라벨 — 막연한 건강 질의와 맞지 않게 그대로 둔다."""
        assert topic_phrase("general") == "general"

    def test_dev_kb_vocabulary_all_korean(self):
        missing = [t for t in DEV_KB_LABELS_2026_09_29
                   if t != "general" and not _HANGUL.search(topic_phrase(t) or "")]
        assert missing == []

    def test_seed_builders_topics_korean(self):
        """시드가 만드는 라벨은 모두 표시어가 있다 — 새 시드가 영문 라벨을 더하면 여기서 걸린다."""
        from seed_checkup_criteria_kb import build_checkup_documents
        from seed_legal_kb import build_legal_documents
        from seed_lifecycle_kb import build_lifecycle_documents
        from seed_navigation_kb import build_navigation_documents
        from seed_reference_ranges import build_cross_reference_documents, build_reference_documents
        from seed_safety_kb import build_safety_documents
        from seed_vaccination_kb import build_vaccination_documents
        labels = set()
        for build in (build_checkup_documents, build_legal_documents, build_lifecycle_documents,
                      build_navigation_documents, build_reference_documents,
                      build_cross_reference_documents, build_safety_documents,
                      build_vaccination_documents):
            labels |= {d.get("evidence_topic") for d in build() if d.get("evidence_topic")}
        assert labels
        missing = sorted(t for t in labels if not _HANGUL.search(topic_phrase(t)))
        assert missing == []


def _provider(vectors):
    """texts → 벡터. 표에 없는 문자열은 질의와 직교하는 벡터."""
    mock = MagicMock()
    mock.embed.side_effect = lambda texts: [vectors.get(t, [0.0, 1.0, 0.0]) for t in texts]
    return mock


class TestAlignmentUsesKoreanPhrase:
    def test_embeds_phrase_not_label(self):
        provider = _provider({"발열": [1.0, 0.0, 0.0], "열이 나요": [1.0, 0.0, 0.0]})
        chunk = {"chunk_id": "c1", "evidence_topic": "fever"}
        check_evidence_topic_alignment([chunk], "열이 나요", provider)
        assert provider.embed.call_args_list[0].args[0] == ["발열"]
        assert chunk["evidence_topic"] == "fever"  # 청크 라벨은 바꾸지 않는다
        assert chunk["topic_alignment_score"] == pytest.approx(1.0)

    def test_gate_counts_korean_topic_match(self):
        """영문 라벨만 비교하던 때는 no_topic_match 로 INSUFFICIENT 였던 모양."""
        q = "공복혈당은 어떤 편인가요?"
        provider = _provider({q: [1.0, 0.0, 0.0], "공복혈당 기준": [0.8, 0.6, 0.0]})
        chunks = [{"chunk_id": "c1", "evidence_topic": "fasting_glucose",
                   "cosine_score": 0.50, "evidence_level": "B"}]
        check_evidence_topic_alignment(chunks, q, provider)
        gate = evaluate_retrieval_gate(chunks)
        assert chunks[0]["topic_alignment_score"] == pytest.approx(0.8)
        assert gate["topic_match_count"] == 1
        assert gate["decision"] == "WEAK_PASS"

    def test_unrelated_topic_still_low(self):
        """무관한 주제는 표시어로 바꿔도 낮게 남는다(게이트가 계속 걸러낸다)."""
        q = "소아 발열"
        provider = _provider({q: [1.0, 0.0, 0.0], "임부 금기 의약품 임신 중 약": [0.0, 0.0, 1.0]})
        chunks = [{"chunk_id": "c1", "evidence_topic": "pregnancy_drug_safety",
                   "cosine_score": 0.50, "evidence_level": "B"}]
        check_evidence_topic_alignment(chunks, q, provider)
        gate = evaluate_retrieval_gate(chunks)
        assert gate["topic_match_count"] == 0
        assert gate["decision"] == "INSUFFICIENT"
        assert "no_topic_match" in gate["blocked_reasons"]

    def test_phrase_hook_is_wired(self):
        assert rag_engine._topic_phrase("fever") == "발열"
