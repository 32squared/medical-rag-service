"""
seed_safety_kb.py — 중독·소아 응급 안전 정보 → KB 적재 (KB 확장 P6).

기존 응급 KB(NEMC 응급처치, seed_emergency_kb 11시나리오)가 다루지 않는
가정 내 중독 사고, 약물 과다복용, 소아 이물질·열성경련, 일산화탄소 중독을
보강한다. 모든 문서는 "검증된 행동 수칙 + 119/응급실 연계" 구조 —
응급 안내는 보수 방향으로만 단정한다(안심 단정 금지).

원문 출처: 응급의료포털(E-Gen), 질병관리청 — 운영 시 원문 검증·갱신.

build_safety_documents()는 순수 함수 — 키/DB/네트워크 없이 테스트 가능.
"""

from __future__ import annotations

import argparse
from typing import Dict, List

_SOURCE_ID = "safety_kr"

_SAFETY_SOURCE = {
    "id": _SOURCE_ID,
    "name": "가정 안전·중독·소아 응급 정보 큐레이션",
    "source_type": "public",
    "license": "kogl_type1",
    "update_frequency": "yearly",
    "is_active": 1,
}

_DOCS_DEF: List[Dict] = [
    {
        "key": "household_poisoning",
        "title": "가정 내 중독 사고 대응 (세제·화학물질 삼킴)",
        "url": "https://www.e-gen.or.kr",
        "topic": "poisoning",
        "keywords": ["중독", "삼킴", "세제", "화학물질", "락스", "응급처치"],
        "content": (
            "가정용 화학제품(세제, 표백제, 살충제 등)을 삼킨 경우의 일반 대응 수칙입니다"
            "(응급의료포털 응급처치 정보 기준).\n\n"
            "- 즉시 할 일: 입안에 남은 물질을 뱉어내게 하고, 의식·호흡을 확인한 뒤 119에 "
            "연락합니다.\n"
            "- 하지 말아야 할 일: 임의로 토하게 하지 마십시오. 특히 표백제·세정제 같은 "
            "부식성 물질과 석유류 제품은 구토 과정에서 식도·기도에 추가 손상을 일으킬 수 "
            "있습니다. 우유나 물을 많이 마시게 하는 것도 자가 판단으로 하지 말고 119 또는 "
            "의료진의 안내를 따르십시오.\n"
            "- 의료기관 방문 시: 삼킨 제품의 용기·라벨(또는 사진)을 지참하면 의료진의 성분 "
            "확인에 큰 도움이 됩니다. 삼킨 시각과 추정량도 기억해 두십시오.\n"
            "- 눈·피부에 묻은 경우: 흐르는 물로 15분 이상 충분히 씻어내고, 통증·시야 이상이 "
            "지속되면 진료를 받으십시오.\n\n"
            "증상이 없어 보여도 제품에 따라 시간이 지나 악화될 수 있으므로, 삼킨 것이 "
            "확인되면 의료기관 확인을 받는 것이 안전합니다."
        ),
    },
    {
        "key": "drug_overdose",
        "title": "약물 과다복용 의심 시 대응",
        "url": "https://www.e-gen.or.kr",
        "topic": "poisoning",
        "keywords": ["약물과다복용", "과량복용", "음독", "아세트아미노펜", "응급"],
        "content": (
            "약을 정해진 용량보다 많이 복용했거나 음독이 의심되는 경우의 일반 대응입니다.\n\n"
            "- 즉시 119에 연락하거나 응급실로 가십시오. 복용한 약의 포장·남은 약·처방전을 "
            "지참하면 치료에 결정적인 도움이 됩니다. 복용 시각과 추정량을 알려주십시오.\n"
            "- 증상이 없어도 위험할 수 있습니다: 특히 아세트아미노펜(해열진통제 성분) "
            "과다복용은 초기에 증상이 거의 없다가 시간이 지나 간 손상이 진행될 수 있어, "
            "증상이 없다는 이유로 지켜보는 것은 위험합니다.\n"
            "- 의식이 처지는 사람에게 억지로 물이나 음식을 먹이지 말고, 구토 시 기도가 막히지 "
            "않도록 옆으로 눕히십시오.\n"
            "- 고의 음독이 의심되는 경우: 신체 치료와 함께 마음의 위기에 대한 도움이 "
            "필요합니다. 본인 또는 주변인이 힘든 상황이라면 자살예방상담전화 109에서 24시간 "
            "상담받을 수 있습니다.\n\n"
            "약 복용 관련 응급 여부의 자가 판단은 위험하므로, 의심되면 즉시 119 또는 "
            "응급실에 문의하는 것이 안전합니다."
        ),
    },
    {
        "key": "child_choking",
        "title": "소아 이물질 삼킴·기도폐쇄 대응 (단추전지·자석 주의)",
        "url": "https://www.e-gen.or.kr",
        "topic": "child_emergency",
        "keywords": ["이물질", "기도폐쇄", "하임리히", "단추전지", "자석", "사레", "소아응급"],
        "content": (
            "아이가 이물질을 삼켰거나 기도가 막힌 경우의 일반 대응입니다(응급의료포털 "
            "응급처치 정보 기준).\n\n"
            "- 즉시 응급실이 필요한 삼킴: 단추형 전지(리튬전지)와 자석 2개 이상은 증상이 "
            "없어도 식도·장 손상을 빠르게 일으킬 수 있어 즉시 응급실 진료가 필요합니다. "
            "날카로운 물체도 마찬가지입니다.\n"
            "- 기도폐쇄 신호: 말을 못 하고 기침 소리가 나오지 않으며 얼굴이 파래지면 완전 "
            "기도폐쇄로 즉시 처치와 119 신고가 필요합니다. 기침을 할 수 있으면 기침을 "
            "계속하도록 격려하고 입에 손을 넣어 빼내려 하지 마십시오(더 밀어 넣을 위험).\n"
            "- 1세 미만 영아: 머리를 아래로 향하게 팔에 엎드려 안고 등 가운데를 손바닥으로 "
            "5회 두드리고, 뒤집어 가슴 가운데를 5회 압박하는 것을 반복합니다.\n"
            "- 1세 이상 소아: 뒤에서 감싸 안아 배꼽 위를 주먹으로 위쪽으로 밀어 올리는 "
            "복부 밀어내기(하임리히법)를 시행합니다.\n"
            "- 의식을 잃으면 즉시 심폐소생술을 시작하고 119의 전화 안내를 따르십시오.\n\n"
            "정확한 처치법은 평소 심폐소생술 교육(대한심폐소생협회, 소방서 교육 등)으로 "
            "익혀두는 것이 가장 안전합니다."
        ),
    },
    {
        "key": "febrile_seizure",
        "title": "소아 열성경련 대응",
        "url": "https://www.e-gen.or.kr",
        "topic": "child_emergency",
        "keywords": ["열성경련", "경련", "경기", "소아", "발열", "응급"],
        "content": (
            "열성경련은 생후 6개월-5세 아이가 열이 오르면서 일으키는 경련으로, 부모에게는 "
            "매우 놀라운 상황이지만 대응 수칙이 정해져 있습니다(응급의료포털·소아청소년과 "
            "일반 안내 기준).\n\n"
            "- 해야 할 일: 아이를 바닥 등 안전한 곳에 옆으로 눕혀 기도를 확보하고, 주변의 "
            "위험한 물건을 치우고, 경련 시작 시각을 확인합니다. 경련 모습을 영상으로 "
            "기록해 두면 진료에 도움이 됩니다.\n"
            "- 하지 말아야 할 일: 입에 손가락·숟가락 등 어떤 것도 넣지 마십시오(질식·손상 "
            "위험). 아이를 흔들거나 사지를 억지로 붙잡지 말고, 경련 중에 해열제를 입으로 "
            "먹이려 하지 마십시오.\n"
            "- 119가 필요한 경우: 경련이 5분 이상 지속되거나, 멈췄다가 다시 반복되거나, "
            "경련 후 의식이 돌아오지 않거나, 호흡이 이상하거나 입술이 파래지면 즉시 119에 "
            "연락하십시오.\n"
            "- 처음 경련한 경우: 경련이 짧게 끝났더라도 첫 경련이라면 원인 확인을 위해 "
            "진료를 받는 것이 안내됩니다.\n\n"
            "대부분의 단순 열성경련은 수 분 내 멈추고 후유증 없이 회복되는 것으로 알려져 "
            "있으나, 위 기준에 해당하면 지체 없이 응급의료를 이용하시기 바랍니다."
        ),
    },
    {
        "key": "co_poisoning",
        "title": "일산화탄소(CO) 중독 예방과 대응 (난방·캠핑)",
        "url": "https://health.kdca.go.kr",
        "topic": "poisoning",
        "keywords": ["일산화탄소", "연탄가스", "CO중독", "캠핑", "난방", "보일러"],
        "content": (
            "일산화탄소는 색·냄새가 없어 알아차리기 어려운 유독가스로, 겨울철 난방기기와 "
            "캠핑(텐트 내 숯·가스 난방)에서 중독 사고가 반복됩니다(질병관리청).\n\n"
            "- 의심 증상: 두통, 어지럼, 메스꺼움, 졸림이 같은 공간의 여러 사람에게 동시에 "
            "나타나면 일산화탄소 중독을 의심해야 합니다.\n"
            "- 즉시 대응: 의심되면 즉시 창문을 열고 그 공간을 벗어나 신선한 공기가 있는 "
            "곳으로 이동한 뒤 119에 연락하십시오. 의식이 처진 사람이 있으면 구조 시 본인의 "
            "안전(환기)을 먼저 확보해야 합니다.\n"
            "- 예방: 밀폐된 텐트·차량 안에서 숯불·가스히터 사용을 피하고, 보일러는 정기 "
            "점검하며, 일산화탄소 경보기를 설치하는 것이 권장됩니다.\n\n"
            "중독이 의심되면 증상이 가벼워 보여도 의료기관 진료가 필요합니다 — 고압산소 "
            "치료 등 전문 치료가 필요한 경우가 있습니다."
        ),
    },
]


def build_safety_documents(defs: List[Dict] = None) -> List[Dict]:
    """안전 정의 → ingest 문서 dict 리스트 (순수 함수)."""
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
                "source_priority": 1,
                "chunk_type": "patient_info",
                "doc_key": d.get("key", ""),
                "severity": "emergency_adjacent",
            },
            "evidence_topic": d.get("topic", "safety"),
            "regulatory_korea": True,
            "topic_keywords": d.get("keywords", []),
        })
    return docs


def _register_source() -> None:
    from kb_ingest import seed_kb_sources
    seed_kb_sources([_SAFETY_SOURCE])
    try:
        from dbcommon import get_conn, _p
        with get_conn() as (conn, cur):
            cur.execute(
                f"UPDATE kb_sources SET priority_rank = 1, jurisdiction = 'KR', "
                f"institution = '응급의료포털·질병관리청 큐레이션' WHERE id = {_p()}",
                (_SOURCE_ID,),
            )
    except Exception as e:
        print(f"[seed_safety] priority_rank 보강 생략: {str(e)[:80]}", flush=True)


def seed_safety_kb(dry_run: bool = False) -> Dict:
    docs = build_safety_documents()
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
            print(f"[seed_safety] ingest 실패 {d['title']}: {str(e)[:100]}", flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description="중독·소아 응급 안전 정보 → KB 적재")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = seed_safety_kb(dry_run=args.dry_run)
    print(f"[seed_safety] 결과: {s}", flush=True)


if __name__ == "__main__":
    main()
