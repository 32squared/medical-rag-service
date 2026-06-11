"""
seed_navigation_kb.py — 의료 이용 내비게이션 정보 → KB 적재 (KB 확장 P4 + P1-2 제도).

"진단 대신 길 안내"는 의료법상 가장 안전하면서 사용자 실용성이 높은 답변 유형.
진료과 선택 가이드, 응급실·야간진료 찾기, 건강보험 제도(HIRA/공단 — P1-2),
국가건강검진 제도, 진료 전 준비를 큐레이션한다.

문구 원칙: 진료과 안내는 "일반적으로 해당 증상을 진료하는 과"의 정보 제공이며
특정 질병의 진단이 아니다. 응급 신호가 있으면 과 선택보다 119/응급실이 우선.

build_navigation_documents()는 순수 함수 — 키/DB/네트워크 없이 테스트 가능.
"""

from __future__ import annotations

import argparse
from typing import Dict, List

_SOURCE_ID = "navigation_kr"

_NAV_SOURCE = {
    "id": _SOURCE_ID,
    "name": "의료 이용 안내 큐레이션 (진료과·응급실·건강보험·검진)",
    "source_type": "public",
    "license": "kogl_type1",
    "update_frequency": "yearly",
    "is_active": 1,
}

_DOCS_DEF: List[Dict] = [
    {
        "key": "department_guide",
        "title": "증상별 진료과 선택 안내 (어느 과에 가야 하나요)",
        "url": "https://www.e-gen.or.kr",
        "topic": "navigation_department",
        "keywords": ["진료과", "어느과", "병원", "내과", "외과", "진료과목"],
        "content": (
            "증상별로 일반적으로 진료하는 과를 안내합니다. 이는 일반 정보이며, 실제 진료 "
            "과정에서 다른 과로 연계될 수 있습니다.\n\n"
            "- 감기 증상, 발열, 소화 문제 등 일반적 증상: 내과 (어린이는 소아청소년과)\n"
            "- 어느 과인지 판단이 어려운 복합 증상: 가정의학과\n"
            "- 가슴 통증, 두근거림, 혈압 문제: 순환기내과(심장내과)\n"
            "- 속쓰림, 복통, 설사·변비 지속: 소화기내과\n"
            "- 기침 지속, 호흡곤란, 천식: 호흡기내과\n"
            "- 두통 지속, 어지럼증, 손발 저림: 신경과\n"
            "- 허리·무릎·어깨 통증, 골절·염좌: 정형외과\n"
            "- 피부 발진, 두드러기, 가려움: 피부과\n"
            "- 눈 충혈, 시력 변화: 안과\n"
            "- 귀·코·목 증상(중이염, 비염, 인후통): 이비인후과\n"
            "- 배뇨 통증, 혈뇨, 잦은 소변: 비뇨의학과\n"
            "- 생리 이상, 임신 관련: 산부인과\n"
            "- 우울·불안·불면이 일상에 지장을 줄 때: 정신건강의학과\n"
            "- 당뇨·갑상선 등 호르몬 관련: 내분비내과\n\n"
            "중요: 심한 가슴통증, 호흡곤란, 의식 저하, 한쪽 마비·언어장애, 대량 출혈 등 "
            "응급 신호가 있으면 진료과 선택보다 즉시 119 또는 응급실 이용이 우선입니다."
        ),
    },
    {
        "key": "emergency_find",
        "title": "응급실·야간진료·휴일약국 찾기 안내",
        "url": "https://www.e-gen.or.kr",
        "topic": "navigation_emergency",
        "keywords": ["응급실", "야간진료", "달빛어린이병원", "휴일약국", "응급의료포털"],
        "content": (
            "응급 및 야간·휴일 의료 이용 안내입니다.\n\n"
            "- 응급의료포털(E-Gen, www.e-gen.or.kr)과 응급의료정보 앱에서 현재 운영 중인 "
            "응급실, 야간·휴일 진료기관, 휴일지킴이약국을 실시간으로 찾을 수 있습니다.\n"
            "- 119에 전화하면 구급 출동뿐 아니라 응급처치 상담과 병원 안내도 받을 수 "
            "있습니다.\n"
            "- 달빛어린이병원: 밤늦게나 휴일에 아이가 아플 때 응급실 대신 이용할 수 있는 "
            "소아 진료기관으로, 평일 야간과 휴일에 운영합니다(지역별 운영 기관은 "
            "응급의료포털에서 확인).\n"
            "- 비응급 야간 증상 상담: 보건복지상담센터 129에서 의료 관련 상담을 받을 수 "
            "있습니다.\n\n"
            "생명이 위급한 상황(의식 없음, 호흡 곤란, 심한 출혈 등)에서는 검색보다 즉시 "
            "119에 연락하는 것이 우선입니다."
        ),
    },
    {
        "key": "insurance_basics",
        "title": "건강보험 급여·비급여와 본인부담 제도 안내",
        "url": "https://www.hira.or.kr",
        "topic": "navigation_insurance",
        "keywords": ["건강보험", "급여", "비급여", "본인부담", "산정특례", "본인부담상한제"],
        "content": (
            "건강보험 진료비 제도의 일반 안내입니다(건강보험심사평가원·국민건강보험공단).\n\n"
            "- 급여: 건강보험이 적용되는 진료 항목으로, 환자는 본인부담금만 냅니다. "
            "외래 본인부담률은 의료기관 종류(의원·병원·상급종합병원)에 따라 다릅니다.\n"
            "- 비급여: 건강보험이 적용되지 않아 전액 본인 부담인 항목입니다. 비급여 진료비는 "
            "의료기관별로 다를 수 있으며, 심평원 누리집에서 기관별 비급여 가격을 비교할 수 "
            "있습니다.\n"
            "- 본인부담상한제: 연간 본인부담금(비급여 제외)이 소득 수준별 상한을 넘으면 "
            "초과분을 공단이 돌려주는 제도입니다.\n"
            "- 산정특례: 암, 희귀질환, 중증난치질환 등으로 등록되면 해당 질환 진료의 "
            "본인부담률이 크게 경감되는 제도입니다(등록 절차는 진단 의료기관과 공단을 통해 "
            "진행).\n"
            "- 진료비 확인 요청: 본인이 낸 진료비가 적정한지 심평원에 확인을 요청할 수 "
            "있습니다.\n\n"
            "구체적인 본인 사례의 적용 여부는 국민건강보험공단(1577-1000) 또는 "
            "심평원(1644-2000)에 확인하시기 바랍니다."
        ),
    },
    {
        "key": "checkup_system",
        "title": "국가건강검진 제도 안내 (대상·주기·사후관리)",
        "url": "https://www.nhis.or.kr",
        "topic": "navigation_checkup",
        "keywords": ["건강검진", "국가검진", "일반검진", "암검진", "영유아검진", "확진검사"],
        "content": (
            "국가건강검진 제도의 일반 안내입니다(국민건강보험공단).\n\n"
            "- 일반건강검진: 20세 이상 성인은 2년에 1회(비사무직 근로자는 매년) 받을 수 "
            "있습니다. 혈압, 혈액검사(혈당·지질 등), 소변검사, 신체계측 등이 포함됩니다.\n"
            "- 국가암검진: 위암(40세 이상, 2년), 대장암(50세 이상, 매년 분변잠혈검사), "
            "간암(고위험군, 6개월), 유방암(40세 이상 여성, 2년), 자궁경부암(20세 이상 여성, "
            "2년), 폐암(54-74세 고위험 흡연력, 2년) 검진이 운영됩니다.\n"
            "- 영유아건강검진: 생후 14일부터 71개월까지 시기별로 발달·건강 검진이 "
            "제공됩니다.\n"
            "- 검진 결과 사후관리: 검진에서 '질환 의심' 판정을 받으면 확진을 위한 추가 검사가 "
            "필요하며, 고혈압·당뇨병 의심자는 일반 의료기관에서 확진 검사 시 본인부담이 "
            "경감되는 제도가 있습니다. 검진 결과는 검진기관 또는 공단 누리집(The건강보험)에서 "
            "확인할 수 있습니다.\n\n"
            "검진 수치가 기준을 벗어났다는 것은 질병의 확정이 아니며, 진단은 의료기관의 "
            "확진 검사로 이루어집니다."
        ),
    },
    {
        "key": "visit_prep",
        "title": "진료 전 준비 안내 (증상 정리·복용약 목록)",
        "url": "",
        "topic": "navigation_visit_prep",
        "keywords": ["진료준비", "문진", "복용약", "증상기록", "진료상담"],
        "content": (
            "진료를 효과적으로 받기 위한 준비 안내입니다.\n\n"
            "- 증상 정리: 언제 시작했는지, 어떤 양상인지(지속/간헐, 악화·완화 요인), 동반 "
            "증상이 있는지 메모해 가면 진료에 도움이 됩니다.\n"
            "- 복용약 목록: 현재 복용 중인 처방약·일반약·건강기능식품 목록(또는 약 봉투 "
            "사진)을 지참하면 중복 처방과 상호작용 확인에 도움이 됩니다.\n"
            "- 과거력·가족력: 진단받은 질환, 수술 이력, 알레르기(약물 알레르기 포함), 주요 "
            "가족력을 알려주시면 좋습니다.\n"
            "- 검사 결과 지참: 최근 건강검진 결과나 타 병원 검사 기록이 있으면 지참하세요.\n"
            "- 질문 준비: 궁금한 점을 미리 적어 가면 진료 시간을 효율적으로 쓸 수 있습니다."
        ),
    },
]


def build_navigation_documents(defs: List[Dict] = None) -> List[Dict]:
    """내비게이션 정의 → ingest 문서 dict 리스트 (순수 함수)."""
    defs = defs if defs is not None else _DOCS_DEF
    docs: List[Dict] = []
    for d in defs:
        title = d.get("title", "")
        if not title:
            continue
        content_md = f"# {title}\n\n{d.get('content', '')}"
        docs.append({
            "title": title,
            "content_md": content_md,
            "source_id": _SOURCE_ID,
            "source_url": (f"{d.get('url','')}#{d.get('key','')}" if d.get("url") else ""),
            "metadata": {
                "evidence_level": "B",
                "source_priority": 2,
                "chunk_type": "patient_info",
                "doc_key": d.get("key", ""),
            },
            "evidence_topic": d.get("topic", "navigation"),
            "regulatory_korea": True,
            "topic_keywords": d.get("keywords", []),
        })
    return docs


def _register_source() -> None:
    from kb_ingest import seed_kb_sources
    seed_kb_sources([_NAV_SOURCE])
    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE kb_sources SET priority_rank = 2, jurisdiction = 'KR', "
                f"institution = '공공기관 안내 큐레이션' WHERE id = {_p()}",
                (_SOURCE_ID,),
            )
    except Exception as e:
        print(f"[seed_nav] priority_rank 보강 생략: {str(e)[:80]}", flush=True)


def seed_navigation_kb(dry_run: bool = False) -> Dict:
    docs = build_navigation_documents()
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
            )
            summary["ingested"] += 1
        except Exception as e:
            print(f"[seed_nav] ingest 실패 {d['title']}: {str(e)[:100]}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description="의료 이용 내비게이션 정보 → KB 적재")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = seed_navigation_kb(dry_run=args.dry_run)
    print(f"[seed_nav] 결과: {s}", flush=True)


if __name__ == "__main__":
    main()
