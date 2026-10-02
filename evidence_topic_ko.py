"""
evidence_topic_ko.py — evidence_topic 라벨 → 한국어 표시어 (근거 게이트 주제 정렬용)
=====================================================================================
KB 청크의 evidence_topic 은 대부분 영문 snake_case 다. 수집기(collect_public_kb.label_evidence_topic)는
42증상 symptom_key 또는 'general' 을 붙이고, 시드는 자체 키('fasting_glucose', 'navigation_department' …)를 쓴다.
rag_engine.check_evidence_topic_alignment 는 이 문자열을 질의와 임베딩 비교해 topic_alignment_score 를 매기고,
evaluate_retrieval_gate 는 0.30(GATE_TOPIC_ALIGNMENT_THRESHOLD) 이상만 주제 일치로 센다. 그런데 영문 라벨과
한국어 질의의 코사인은 0.1대라('fasting_glucose' ↔ '공복혈당은 어떤 편인가요?' 0.13, '공복혈당' 은 0.83)
라벨이 붙은 청크가 거의 주제 일치로 잡히지 않았다(2026-09-29 dev 재현: 검색된 청크의 4%).

비교할 때만 라벨을 이 표시어로 바꾼다 — DB 의 라벨·수집기·시드는 그대로다(데이터 이관 없음).
  - 증상 키: symptom_catalog 의 symptom_name ('fever' → '발열')
  - 그 밖의 라벨: _TOPIC_KO
  - 한글이 든 라벨(검진 판정기준 시드 등)·모르는 라벨: 그대로
  - 'general'(수집기가 42증상에 못 맞춘 문서, dev KB 의 27%): 주제 정보가 없어 그대로 둔다.
    '일반 건강 정보' 로 바꾸면 '내 건강상태 어때?' 같은 막연한 질의와 0.3 이상으로 맞았다(210 질의 중 16).
"""
import re
from functools import lru_cache

_HANGUL = re.compile(r"[가-힣]")

# 증상 키가 아닌 라벨 (2026-09-29 dev KB 어휘 기준, 'general' 제외). 증상 키는 symptom_catalog 에서 가져온다.
_TOPIC_KO = {
    # 상담 시드·응급
    "aed_usage": "자동심장충격기(AED) 사용법",
    "cardiac_arrest": "심정지 심폐소생술(CPR)",
    "chronic_cough": "오래가는 기침(만성 기침)",
    "emergency_signs": "응급 위험 신호 응급처치",
    "child_emergency": "어린이 응급 상황 이물질 삼킴 열성경련",
    "poisoning": "중독 사고 세제 삼킴 일산화탄소",
    # 증상 문진 가이드 (범주별)
    "consultation_cardiovascular": "심혈관 증상 문진 가슴 통증 두근거림 혈압",
    "consultation_dermatology": "피부 증상 문진 발진 가려움 여드름",
    "consultation_digestive": "소화기 증상 문진 복통 속쓰림 설사 변비",
    "consultation_ent": "귀 코 목 증상 문진 이비인후과",
    "consultation_mental": "정신건강 증상 문진 불면 스트레스 불안 우울",
    "consultation_musculoskeletal": "근골격 증상 문진 허리 무릎 어깨 근육 통증",
    "consultation_neuro": "신경 증상 문진 두통 어지럼 저림 경련 기억력",
    "consultation_respiratory": "호흡기 증상 문진 기침 숨참 흉통",
    "consultation_systemic": "전신 증상 문진 발열 피로 체중 변화",
    "consultation_urogenital": "비뇨생식기 증상 문진 빈뇨 배뇨통 혈뇨 생리",
    # 식약처 DUR
    "age_drug_safety": "연령 금기 의약품",
    "drug_administration": "서방정 분할 주의 의약품",
    "drug_dosage": "의약품 용량 주의",
    "drug_duplication": "효능군 중복 의약품",
    "drug_duration": "투여 기간 주의 의약품",
    "drug_interaction": "병용 금기 의약품 함께 먹으면 안 되는 약",
    "elderly_drug_safety": "노인 주의 의약품",
    "pregnancy_drug_safety": "임부 금기 의약품 임신 중 약",
    # 생애주기·만성질환
    "cancer_general": "암 진단 후 치료 과정",
    "cancer_screening": "국가 암검진 위암 대장암 간암 유방암 자궁경부암 폐암",
    "dementia": "치매 조기 발견",
    "diabetes": "당뇨병",
    "diabetes_care": "당뇨병 생활관리",
    "elderly_fall": "노인 낙상 예방",
    "elderly_medication": "노인 여러 약 복용(다약제)",
    "hypertension_care": "고혈압 생활관리",
    "mental_health": "우울 불안 정신건강",
    "pregnancy": "임신 중 건강관리",
    "rare_disease": "희귀질환 지원 제도",
    "respiratory_care": "천식 COPD 생활관리",
    "sleep": "수면 위생 잠 잘 자는 법",
    "vaccination": "예방접종 일정 독감 폐렴구균 국가예방접종",
    # 측정값 참조 기준
    "blood_pressure": "혈압 기준",
    "bmi": "체질량지수(BMI) 비만 기준",
    "body_temperature": "체온 기준",
    "co2_indoor": "실내 이산화탄소 환기 기준",
    "fasting_glucose": "공복혈당 기준",
    "hba1c": "당화혈색소(HbA1c) 기준",
    "heart_rate": "심박수 맥박 기준",
    "metabolic": "혈압과 체중 비만",
    "pm10": "미세먼지(PM10) 기준",
    "pm25": "초미세먼지(PM2.5) 기준",
    "spo2": "산소포화도(SpO2) 기준",
    # 의료 이용 안내
    "navigation_checkup": "국가건강검진 대상 주기",
    "navigation_department": "증상별 진료과 선택 어느 과",
    "navigation_emergency": "응급실 야간진료 휴일약국 찾기",
    "navigation_insurance": "건강보험 급여 비급여 본인부담",
    "navigation_visit_prep": "진료 전 준비 증상 정리 복용약 목록",
    # 법령·의료법 가이드(내부 지침)
    "legal_emergency": "응급의료법 응급환자 안내",
    "legal_medical_advertising": "의료광고 금지",
    "legal_privacy": "민감정보 개인정보 처리",
    "legal_unlicensed_practice": "무면허 의료행위 금지",
    "diagnosis": "병명 단정 확정 진단 금지",
    "emergency_dismiss": "응급 내원 필요성 부정 금지",
    "hospital_referral": "병원 의사 알선 금지",
    "impersonation": "의료인 사칭 금지",
    "personalized_treatment": "개인 맞춤 치료 계획 금지",
    "post_procedure_advice": "시술 후 관리 지시 금지",
    "prescription": "처방 복약 용량 지시 금지",
    "risk_probability": "위험도 사망률 확률 제시 금지",
    "test_procedure": "검사 시술 치료 지시 금지",
}


@lru_cache(maxsize=1)
def _symptom_names() -> dict:
    """symptom_key → symptom_name (symptom_catalog: 42증상 + 보강). 실패하면 빈 표."""
    try:
        import symptom_catalog
        return {
            (v.get("symptom_key") or k): v["symptom_name"]
            for k, v in symptom_catalog.load_catalog().items()
            if isinstance(v, dict) and v.get("symptom_name")
        }
    except Exception:
        return {}


def topic_phrase(label):
    """주제 정렬 비교에 쓸 문자열. 한글이 든 라벨·모르는 라벨·빈 값은 그대로 돌려준다."""
    if not label or _HANGUL.search(label):
        return label
    return _TOPIC_KO.get(label) or _symptom_names().get(label) or label
