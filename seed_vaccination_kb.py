"""
seed_vaccination_kb.py — 국가예방접종(NIP) 정보 → KB 적재 (KB 확장 P1-1).

retrieval_router의 vaccination intent가 primary로 라우팅하는 'NIP' 출처가
비어있는 공백을 메운다. 질병관리청 예방접종도우미(nip.kdca.go.kr) 공개 정보의
핵심을 큐레이션 — 정확한 최신 일정·지원 대상은 운영 시 원문으로 검증·갱신한다
(source_url 보존, 일정은 연도별 고시로 변동 가능).

문구 원칙: 접종 권고는 "국가예방접종 일정상 안내"의 사실 전달 + 의료기관 상담 연결.
개인별 접종 가부 판단(금기 해당 여부 등)은 의료진 상담으로 안내한다.

build_vaccination_documents()는 순수 함수 — 키/DB/네트워크 없이 테스트 가능.
"""

from __future__ import annotations

import argparse
from typing import Dict, List

_SOURCE_ID = "nip"

_NIP_SOURCE = {
    "id": _SOURCE_ID,
    "name": "질병관리청 예방접종도우미 (국가예방접종 NIP)",
    "source_type": "public",
    "license": "kogl_type1",
    "update_frequency": "yearly",
    "is_active": 1,
}

_BASE_URL = "https://nip.kdca.go.kr"

_DOCS_DEF: List[Dict] = [
    {
        "key": "nip_child_schedule",
        "title": "어린이 국가예방접종(NIP) 표준 일정 안내",
        "topic": "vaccination",
        "keywords": ["예방접종", "백신", "어린이", "영유아", "표준일정", "NIP"],
        "content": (
            "국가예방접종(NIP)은 국가가 권장하고 비용을 지원하는 예방접종으로, "
            "지정 의료기관과 보건소에서 무료로 접종할 수 있습니다. 어린이 표준 예방접종 일정의 "
            "주요 항목은 다음과 같습니다.\n\n"
            "- BCG(결핵): 생후 4주 이내\n"
            "- B형간염: 출생 시, 1개월, 6개월 (총 3회)\n"
            "- DTaP(디프테리아·파상풍·백일해): 2·4·6개월, 추가접종 15-18개월, 4-6세\n"
            "- 폴리오(IPV): 2·4·6-18개월, 4-6세\n"
            "- Hib(b형 헤모필루스 인플루엔자): 2·4·6개월, 추가 12-15개월\n"
            "- 폐렴구균(PCV): 2·4·6개월, 추가 12-15개월\n"
            "- MMR(홍역·유행성이하선염·풍진): 12-15개월, 4-6세\n"
            "- 수두: 12-15개월\n"
            "- 일본뇌염: 12개월 이후 (사백신/생백신에 따라 일정 상이)\n"
            "- A형간염: 12-23개월에 1차, 6개월 이상 간격으로 2차\n"
            "- HPV(사람유두종바이러스): 12세 (지원 대상·범위는 연도별 고시 확인)\n"
            "- 인플루엔자: 생후 6개월-13세 어린이 매년 접종 지원\n\n"
            "정확한 접종 시기와 지원 대상은 연도별로 변경될 수 있으므로 "
            "예방접종도우미 누리집 또는 보건소에서 확인하시기 바랍니다. 접종 전 아이의 "
            "건강 상태(발열, 급성 질환 등)에 따른 접종 가능 여부는 접종 기관의 의사가 "
            "예진을 통해 판단합니다."
        ),
    },
    {
        "key": "nip_adult",
        "title": "성인 예방접종 안내 (인플루엔자·폐렴구균 등)",
        "topic": "vaccination",
        "keywords": ["예방접종", "성인", "인플루엔자", "폐렴구균", "대상포진", "파상풍"],
        "content": (
            "성인에게 권장되는 주요 예방접종 정보입니다.\n\n"
            "- 인플루엔자(독감): 매년 1회 접종이 권장되며, 65세 이상 어르신은 "
            "국가예방접종 지원 대상입니다.\n"
            "- 폐렴구균: 65세 이상에서 국가 지원 접종이 안내되고 있습니다. 만성질환자 등 "
            "위험군의 접종 일정은 의료기관과 상담이 필요합니다.\n"
            "- 파상풍·디프테리아(Td/Tdap): 매 10년마다 추가 접종이 권장됩니다.\n"
            "- 대상포진: 50세 이상 성인에서 접종이 권고되는 백신이 있습니다(국가지원 여부는 "
            "연도별 정책 확인 필요).\n"
            "- B형간염: 항체가 없는 성인에게 3회 접종이 권장됩니다.\n\n"
            "기저질환이 있거나 면역저하 상태인 경우 접종 가능 여부와 우선순위가 다를 수 "
            "있으므로, 본인의 건강 상태에 맞는 접종 계획은 의사와 상담하여 결정하시기 바랍니다."
        ),
    },
    {
        "key": "nip_pregnant",
        "title": "임신부 예방접종 안내",
        "topic": "vaccination",
        "keywords": ["예방접종", "임신부", "임산부", "인플루엔자", "Tdap", "생백신"],
        "content": (
            "임신 중 예방접종에 관한 일반 정보입니다.\n\n"
            "- 인플루엔자(독감): 임신부는 인플루엔자 합병증 위험이 높아 임신 주수와 관계없이 "
            "접종이 권장되며, 국가예방접종 지원 대상입니다(사백신).\n"
            "- Tdap(파상풍·디프테리아·백일해): 신생아 백일해 예방을 위해 임신 27-36주에 "
            "접종이 권고됩니다.\n"
            "- 생백신(MMR, 수두 등): 임신 중에는 접종하지 않는 것이 원칙입니다. 가임기 여성은 "
            "접종 후 일정 기간 임신을 피하도록 안내됩니다.\n\n"
            "개별 접종의 시기와 가능 여부는 산모와 태아의 상태에 따라 다르므로, 반드시 "
            "산부인과 의사와 상담 후 결정하시기 바랍니다."
        ),
    },
    {
        "key": "nip_adverse",
        "title": "예방접종 후 이상반응 안내와 대처",
        "topic": "vaccination",
        "keywords": ["예방접종", "이상반응", "부작용", "발열", "접종부위"],
        "content": (
            "예방접종 후 나타날 수 있는 반응과 일반적인 대처 정보입니다.\n\n"
            "- 흔한 반응: 접종 부위의 통증·부기·발적, 가벼운 발열, 보챔(영유아)은 비교적 "
            "흔하며 대부분 1-2일 내 호전됩니다.\n"
            "- 진료가 필요한 경우: 고열이 지속되거나, 경련, 의식 저하, 심한 보챔, 접종 부위의 "
            "심한 부기·화농이 있으면 의료기관 진료를 받으시기 바랍니다.\n"
            "- 즉시 응급조치가 필요한 경우: 접종 직후 두드러기·호흡곤란·어지러움 등 "
            "아나필락시스가 의심되면 즉시 119에 연락하거나 응급실을 이용하시기 바랍니다. "
            "이러한 급성 반응 관찰을 위해 접종 후 20-30분간 접종기관에서 대기하는 것이 "
            "권장됩니다.\n"
            "- 이상반응 신고: 예방접종 후 이상반응이 의심되면 예방접종도우미 누리집 또는 "
            "보건소를 통해 신고할 수 있으며, 국가 보상제도가 운영되고 있습니다."
        ),
    },
    {
        "key": "nip_flu_support",
        "title": "인플루엔자(독감) 국가예방접종 지원 대상 안내",
        "topic": "vaccination",
        "keywords": ["인플루엔자", "독감", "국가예방접종", "지원대상", "무료접종"],
        "content": (
            "인플루엔자 국가예방접종 지원사업의 일반 안내입니다.\n\n"
            "- 지원 대상(통상): 생후 6개월-13세 어린이, 임신부, 65세 이상 어르신\n"
            "- 접종 시기: 매년 가을(통상 9-11월경) 시작되며, 대상군별 시작 시기가 다를 수 "
            "있습니다.\n"
            "- 접종 장소: 지정 의료기관 및 보건소\n\n"
            "연도별 지원 대상·기간은 변경될 수 있으므로 예방접종도우미 누리집에서 당해 연도 "
            "공고를 확인하시기 바랍니다. 달걀 알레르기 등 접종 관련 우려가 있는 경우 접종 전 "
            "의사와 상담하시기 바랍니다."
        ),
    },
]


def build_vaccination_documents(defs: List[Dict] = None) -> List[Dict]:
    """예방접종 정의 → ingest 문서 dict 리스트 (순수 함수)."""
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
            "source_url": f"{_BASE_URL}#{d.get('key','')}",
            "metadata": {
                "evidence_level": "A",
                "source_priority": 2,
                "chunk_type": "patient_info",
                "doc_key": d.get("key", ""),
            },
            "evidence_topic": d.get("topic", "vaccination"),
            "regulatory_korea": True,
            "topic_keywords": d.get("keywords", []),
        })
    return docs


def _register_source() -> None:
    """nip 출처 등록(멱등) + priority_rank=2(NIP 라벨) 보강."""
    from kb_ingest import seed_kb_sources
    seed_kb_sources([_NIP_SOURCE])
    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE kb_sources SET priority_rank = 2, jurisdiction = 'KR', "
                f"institution = '질병관리청', url = {_p()} WHERE id = {_p()}",
                (_BASE_URL, _SOURCE_ID),
            )
    except Exception as e:
        print(f"[seed_nip] priority_rank 보강 생략: {str(e)[:80]}", flush=True)


def seed_vaccination_kb(dry_run: bool = False) -> Dict:
    """NIP 예방접종 정보 → KB 적재."""
    docs = build_vaccination_documents()
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
            print(f"[seed_nip] ingest 실패 {d['title']}: {str(e)[:100]}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description="국가예방접종(NIP) 정보 → KB 적재")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = seed_vaccination_kb(dry_run=args.dry_run)
    print(f"[seed_nip] 결과: {s}", flush=True)


if __name__ == "__main__":
    main()
