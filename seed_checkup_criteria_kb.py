"""
seed_checkup_criteria_kb.py — 국가건강검진 판정기준 → KB 적재.

출처: 보건복지부 고시 제2026-6호 「건강검진 실시기준」 [별표 4] 건강검진 판정기준과
별첨 「검사항목별 판정기준」(2026-01-07 시행). 고시는 저작권법 제7조의 보호받지 못하는
저작물이라 기준 수치를 옮겨 적을 수 있다(문장은 쉬운 말로 다시 썼다).

왜: PHR 사용자는 검진표의 '정상B'·'질환의심'이 무슨 뜻인지, 공복혈당·콜레스테롤 수치가
어느 기준에 드는지를 묻는데 KB 에 검진 판정기준 문서가 없었다(dev 실측 — 검진 질문 근거
게이트 INSUFFICIENT 96%, 공복혈당 질문 38/38).

문구 원칙:
- 검진 판정은 선별 결과이며 진단이 아니다 — '질환의심'은 진료·검사로 확인이 필요하다는 뜻.
- 기준표는 일반 정보다. 개인 값의 해석과 이후 검사·진료 여부는 의료진이 판단한다.
- 항목이 여럿인 문서는 항목마다 '## ' 절로 나눈다 — 절이 청크가 된다. 표 전체가 한 청크면
  짧은 질문과 코사인이 낮다('콜레스테롤 수치 괜찮은 건가요?' 0.27 → 절 분리 0.44).
- '검사 결과'라는 말을 쓰지 않는다 — 공용 analyzer 가 이 말만으로 diagnosis CRITICAL 을
  잡는다. 답변이 KB 문장을 옮겨 쓰면 가드레일 차단으로 이어진다.
- vital_rules.PERSONAL_BAND_DENY 항목(LDL·eGFR·골밀도·요단백)은 기준 수치를 싣지 않는다 —
  동반 질환·나이·반복 검사에 따라 해석이 달라져 RAG 가 개인 구간 분류를 막는 항목이다.
- evidence_topic 은 사용자가 쓰는 한국어 낱말로 쓴다 — 근거 게이트가 이 문자열을 질의와
  임베딩 비교하는데 영문 snake_case('fasting_glucose')는 한국어 질의와 0.13~0.15 로
  문턱(0.30)을 넘지 못한다.

build_checkup_documents()는 순수 함수 — 키/DB/네트워크 없이 테스트 가능.
"""

from __future__ import annotations

import argparse
from typing import Dict, List

_SOURCE_ID = "checkup_std_kr"
_URL = "https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000272270"

_CHECKUP_SOURCE = {
    "id": _SOURCE_ID,
    "name": "국가건강검진 판정기준 (보건복지부 고시 「건강검진 실시기준」)",
    "source_type": "guideline",
    "license": "public_domain",  # 고시 — 저작권법 제7조 비보호 저작물
    "update_frequency": "yearly",
    "is_active": 1,
}

_SOURCE_LINE = (
    "출처: 보건복지부 고시 제2026-6호 「건강검진 실시기준」 [별표 4] 건강검진 판정기준 및 "
    "별첨 「검사항목별 판정기준」(2026년 1월 7일 시행)"
)
_DISCLAIMER = (
    "이 기준은 국가건강검진 결과표를 읽기 위한 일반 정보입니다. 검진 판정은 선별 결과이며 "
    "진단이 아닙니다. 개인 수치의 해석과 이후 검사·진료 여부는 의료진이 판단합니다."
)


def _deny_line() -> str:
    """개인 구간 분류 금지 항목 안내 — vital_rules 목록을 그대로 따른다."""
    from vital_rules import personal_band_deny_names
    return (
        f"{personal_band_deny_names()} 수치는 나이, 동반 질환, 반복 검사 여부 등 개인 상태에 "
        "따라 해석이 달라지므로 의료진이 판단합니다."
    )


_DOCS_DEF: List[Dict] = [
    {
        "key": "overview",
        "title": "국가건강검진 결과 판정 구분 안내 (정상A·정상B·질환의심·유질환자)",
        "topic": "건강검진 결과 판정 정상A 정상B 질환의심",
        "keywords": ["건강검진", "검진 결과", "판정", "정상A", "정상B", "경계", "질환의심",
                     "유질환자", "결과표"],
        "content": (
            "국가건강검진 결과표에는 검사 항목별 결과와 함께 판정 구분이 적혀 있습니다. "
            "판정 구분의 뜻은 보건복지부 고시 「건강검진 실시기준」에 다음과 같이 정해져 있습니다.\n\n"
            "- 정상A: 건강이 양호한 경우입니다.\n"
            "- 정상B(경계): 이상은 없으나 식생활 습관이나 환경 개선 같은 자가 관리와 예방 조치가 "
            "필요한 경우입니다.\n"
            "- 일반 질환의심: 질환으로 발전할 가능성이 있어 추적검사나 전문 의료기관에서 정확한 "
            "진단과 치료가 필요한 경우입니다.\n"
            "- 고혈압·당뇨병·이상지질혈증 질환의심: 해당 질환이 의심되어 진료와 검사 등이 필요한 "
            "경우입니다.\n"
            "- 유질환자: 고혈압, 당뇨병, 이상지질혈증, 폐결핵, 우울증, 조기정신증, C형간염, "
            "만성폐쇄성폐질환을 진단받고 현재 약물 치료 중인 경우입니다.\n\n"
            "## 질환의심의 뜻과 개인 수치 해석 (국가건강검진)\n\n"
            "판정은 항목별 기준표(혈압, 비만, 빈혈, 공복혈당, 콜레스테롤·중성지방, 간 수치, "
            "신장 기능 등)에 따라 정해집니다.\n\n"
            "'질환의심'은 선별검사에서 추가 확인이 필요하다는 뜻이며, 그 자체로 질환을 확정하는 "
            "진단이 아닙니다. 확인을 위한 검사와 진료 여부는 의료진이 판단합니다.\n\n"
            "{deny_line}"
        ),
    },
    {
        "key": "blood_pressure",
        "title": "국가건강검진 혈압 판정기준 (고혈압 선별)",
        "topic": "혈압 건강검진 판정기준",
        "keywords": ["혈압", "수축기", "이완기", "고혈압", "건강검진", "판정기준", "mmHg"],
        "content": (
            "국가건강검진의 혈압 판정기준입니다(단위 mmHg).\n\n"
            "- 정상A: 수축기 120 미만이면서 이완기 80 미만\n"
            "- 정상B(경계): 수축기 120~139 또는 이완기 80~89\n"
            "- 고혈압 질환의심: 수축기 140 이상 또는 이완기 90 이상\n\n"
            "정상A는 수축기와 이완기가 모두 기준 안이어야 하고, 정상B와 질환의심은 둘 중 하나만 "
            "해당해도 그 구분에 듭니다.\n\n"
            "'고혈압 질환의심'은 고혈압이 의심되어 진료와 검사가 필요하다는 뜻입니다. 혈압은 잴 "
            "때마다 달라질 수 있어 고혈압 여부는 진료 과정에서 의료진이 확인합니다."
        ),
    },
    {
        "key": "obesity",
        "title": "국가건강검진 비만 판정기준 (체질량지수·허리둘레)",
        "topic": "체질량지수 BMI 허리둘레 비만 검진 판정기준",
        "keywords": ["비만", "체질량지수", "BMI", "허리둘레", "복부비만", "저체중", "건강검진",
                     "판정기준"],
        "content": (
            "## 체질량지수(BMI) 기준 (국가건강검진)\n\n"
            "체질량지수(kg/㎡)는 몸무게(kg)를 키(m)의 제곱으로 나눈 값입니다.\n"
            "- 정상A: 18.5~24.9\n"
            "- 정상B(경계): 25~29.9, 또는 18.5 미만(저체중)\n"
            "- 비만 질환의심: 30 이상\n\n"
            "## 허리둘레 기준 (국가건강검진)\n\n"
            "- 정상A: 남성 90cm 미만, 여성 85cm 미만\n"
            "- 질환의심: 남성 90cm 이상, 여성 85cm 이상\n\n"
            "체중과 허리둘레 관리 방법은 개인 상태에 따라 다르므로 의료진과 상담하세요."
        ),
    },
    {
        "key": "anemia",
        "title": "국가건강검진 빈혈 판정기준 (혈색소)",
        "topic": "혈색소 헤모글로빈 빈혈 검진 판정기준",
        "keywords": ["빈혈", "혈색소", "헤모글로빈", "Hb", "건강검진", "판정기준"],
        "content": (
            "국가건강검진에서 빈혈을 선별하는 혈색소(헤모글로빈) 판정기준입니다(단위 g/dL).\n\n"
            "남성\n"
            "- 정상A: 13.0~16.5\n"
            "- 정상B(경계): 12.0~12.9\n"
            "- 빈혈 질환의심: 12.0 미만\n\n"
            "여성\n"
            "- 정상A: 12.0~15.5\n"
            "- 정상B(경계): 10.0~11.9\n"
            "- 빈혈 질환의심: 10.0 미만\n\n"
            "이 기준표는 혈색소가 낮은 쪽(빈혈)을 선별하기 위한 것입니다. 정상A 범위보다 높은 "
            "값을 포함해 개인의 혈색소 결과 해석은 의료진이 판단합니다."
        ),
    },
    {
        "key": "fasting_glucose",
        "title": "국가건강검진 공복혈당 판정기준 (당뇨병 선별)",
        "topic": "공복혈당 당뇨병 검진 판정기준",
        "keywords": ["공복혈당", "혈당", "당뇨", "당뇨병", "공복", "건강검진", "판정기준",
                     "mg/dL"],
        "content": (
            "국가건강검진의 공복혈당 판정기준입니다(단위 mg/dL).\n\n"
            "- 정상A: 100 미만\n"
            "- 정상B(경계): 100~125\n"
            "- 당뇨병 질환의심: 126 이상\n\n"
            "공복혈당은 검사 전 금식한 상태에서 잰 혈당입니다. '당뇨병 질환의심'은 당뇨병이 "
            "의심되어 진료와 검사가 필요하다는 뜻이며, 당뇨병 여부는 추가 검사를 거쳐 의료진이 "
            "판단합니다. 정상B(경계)는 식생활 등 생활 습관 관리와 예방 조치가 필요한 구간으로 "
            "정해져 있습니다."
        ),
    },
    {
        "key": "lipids",
        "title": "국가건강검진 이상지질혈증 판정기준 (총콜레스테롤·HDL·중성지방)",
        "topic": "콜레스테롤 중성지방 이상지질혈증 검진 판정기준",
        "keywords": ["콜레스테롤", "총콜레스테롤", "HDL", "고밀도", "중성지방", "이상지질혈증",
                     "고지혈증", "건강검진", "판정기준"],
        "content": (
            "## 총콜레스테롤 수치 기준 (국가건강검진, mg/dL)\n\n"
            "- 정상A: 200 미만\n"
            "- 정상B(경계): 200~239\n"
            "- 질환의심: 240 이상\n\n"
            "## 고밀도(HDL) 콜레스테롤 수치 기준 (국가건강검진, mg/dL)\n\n"
            "- 정상A: 60 이상\n"
            "- 정상B(경계): 40~59\n"
            "- 질환의심: 40 미만\n\n"
            "고밀도(HDL) 콜레스테롤은 다른 항목과 달리 값이 낮은 쪽이 기준에서 벗어난 쪽입니다.\n\n"
            "## 중성지방 수치 기준 (국가건강검진, mg/dL)\n\n"
            "- 정상A: 150 미만\n"
            "- 정상B(경계): 150~199\n"
            "- 질환의심: 200 이상\n\n"
            "## 저밀도(LDL) 콜레스테롤 (국가건강검진)\n\n"
            "저밀도(LDL) 콜레스테롤은 당뇨병 같은 동반 질환이나 심뇌혈관 질환 위험도에 따라 "
            "기준이 달라지며, 고시의 기준표에도 의사 판단에 따라 달리 적용할 수 있다는 주석이 "
            "있습니다. 저밀도(LDL) 콜레스테롤 결과의 해석은 의료진이 개인 상태를 보고 판단합니다.\n\n"
            "'이상지질혈증 질환의심'은 진료와 검사가 필요하다는 뜻이며, 진단과 관리 방법은 "
            "의료진이 정합니다."
        ),
    },
    {
        "key": "liver",
        "title": "국가건강검진 간기능 판정기준 (AST·ALT·감마지티피)",
        "topic": "간 수치 간기능 AST ALT 감마지티피",
        "keywords": ["간수치", "간 수치", "간기능", "AST", "ALT", "SGOT", "SGPT", "감마지티피",
                     "γ-GTP", "GGT", "건강검진", "판정기준"],
        "content": (
            "## 간 수치 — AST(에이에스티, SGOT) 기준 (국가건강검진, U/L)\n\n"
            "- 정상A: 40 이하\n"
            "- 정상B(경계): 41~50\n"
            "- 질환의심: 51 이상\n\n"
            "## 간 수치 — ALT(에이엘티, SGPT) 기준 (국가건강검진, U/L)\n\n"
            "- 정상A: 35 이하\n"
            "- 정상B(경계): 36~45\n"
            "- 질환의심: 46 이상\n\n"
            "## 간 수치 — 감마지티피(γ-GTP) 기준 (국가건강검진, U/L)\n\n"
            "- 남성: 정상A 11~63, 정상B(경계) 64~77, 질환의심 78 이상\n"
            "- 여성: 정상A 8~35, 정상B(경계) 36~45, 질환의심 46 이상\n\n"
            "간 수치는 여러 요인의 영향을 받을 수 있어, 결과의 의미와 추가 검사 여부는 의료진이 "
            "판단합니다."
        ),
    },
    {
        "key": "kidney",
        "title": "국가건강검진 신장 기능 판정기준 (혈청크레아티닌·eGFR·요단백)",
        "topic": "신장 기능 수치 크레아티닌 콩팥",
        "keywords": ["신장", "콩팥", "신장기능", "크레아티닌", "혈청크레아티닌", "사구체여과율",
                     "eGFR", "요단백", "건강검진", "판정기준"],
        "content": (
            "## 신장 기능 수치 — 크레아티닌 기준 (국가건강검진, mg/dL)\n\n"
            "혈청크레아티닌은 신장(콩팥) 기능을 볼 때 쓰는 혈액 수치입니다.\n"
            "- 정상A: 1.5 이하\n"
            "- 질환의심: 1.5 초과\n\n"
            "## 신장 기능 수치 — 사구체여과율(eGFR)·요단백 (국가건강검진)\n\n"
            "국가건강검진의 신장질환 선별 항목은 요단백, 혈청크레아티닌, 신사구체여과율(eGFR)"
            "입니다. 요단백과 사구체여과율(eGFR)은 나이, 동반 질환, 반복 검사 여부 등을 함께 "
            "보아야 해석할 수 있어 의료진이 개인 상태에 따라 판단합니다.\n\n"
            "신장 기능 결과의 의미와 추가 검사 여부는 의료진이 판단합니다."
        ),
    },
]


def build_checkup_documents(defs: List[Dict] = None) -> List[Dict]:
    """판정기준 정의 → ingest 문서 dict 리스트 (순수 함수)."""
    defs = defs if defs is not None else _DOCS_DEF
    docs: List[Dict] = []
    for d in defs:
        title = d.get("title", "")
        if not title:
            continue
        body = d.get("content", "").replace("{deny_line}", _deny_line())
        content_md = f"# {title}\n\n{body}\n\n{_SOURCE_LINE}\n\n{_DISCLAIMER}"
        docs.append({
            "title": title,
            "content_md": content_md,
            "source_id": _SOURCE_ID,
            "source_url": _URL,
            "metadata": {
                "evidence_level": "A",
                "source_priority": 2,
                "chunk_type": "reference_range",
                "doc_key": d.get("key", ""),
                "source_version": "보건복지부 고시 제2026-6호 (2026-01-07 시행)",
            },
            "evidence_topic": d.get("topic", "건강검진 판정기준"),
            "regulatory_korea": True,
            "topic_keywords": d.get("keywords", []),
        })
    return docs


def _register_source() -> None:
    from kb_ingest import seed_kb_sources
    seed_kb_sources([_CHECKUP_SOURCE])
    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE kb_sources SET priority_rank = 2, jurisdiction = 'KR', "
                f"institution = '보건복지부' WHERE id = {_p()}",
                (_SOURCE_ID,),
            )
    except Exception as e:
        print(f"[seed_checkup] priority_rank 보강 생략: {str(e)[:80]}", flush=True)


def seed_checkup_criteria_kb(dry_run: bool = False) -> Dict:
    docs = build_checkup_documents()
    summary = {"documents": len(docs), "ingested": 0}
    if dry_run:
        summary["dry_run"] = True
        return summary

    _register_source()
    import kb_ingest
    for d in docs:
        try:
            kb_ingest.ingest_document(
                title=d["title"], content_md=d["content_md"], source_id=d["source_id"],
                metadata=d["metadata"], evidence_country="KR",
                evidence_topic=d["evidence_topic"], regulatory_korea=d["regulatory_korea"],
                topic_keywords=d["topic_keywords"], source_url=d.get("source_url", ""),
                upsert=True, status="active",
                match_url=False,  # 기관 대표 URL 공유 — 제목으로 식별(kb_ingest 참고)
            )
            summary["ingested"] += 1
        except Exception as e:
            print(f"[seed_checkup] ingest 실패 {d['title']}: {str(e)[:100]}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description="국가건강검진 판정기준 → KB 적재")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = seed_checkup_criteria_kb(dry_run=args.dry_run)
    print(f"[seed_checkup] 결과: {s}", flush=True)


if __name__ == "__main__":
    main()
