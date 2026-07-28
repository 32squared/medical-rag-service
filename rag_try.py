#!/usr/bin/env python
"""
rag_try.py — 로컬 오프라인 RAG 테스트 하니스.

PostgreSQL·OpenAI 키 없이도 RAG의 핵심 동작(분류 · 안전분기 · 진료과 트리아지 ·
거절→길안내 · 인용검증 · 멀티턴 후속질의 재작성)을 즉시 시험할 수 있다.
내부적으로 medical_rag_pipeline.process_medical_query(mock LLM 내장)를 사용하고,
대화형 모드에서는 followup_rewriter/conversation_context로 멀티턴을 시연한다.

사용법:
  python rag_try.py "배가 아파요"        # 단발 질의
  python rag_try.py                       # 대화형 REPL (멀티턴: 이어지는 질문에 직전 주제 적용)
  python rag_try.py --json "두통"         # 결과 전체 JSON 출력

라이브 모드(실검색+실LLM)는 DATABASE_URL(PostgreSQL) + OPENAI_API_KEY 설정 후
rag_server.py / generate_response 경로로 동작한다(이 하니스는 오프라인 전용).
"""

import io
import os
import sys
import json

# 한글 출력 보장 (Windows 콘솔)
if __name__ == "__main__":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from medical_rag_pipeline import process_medical_query
from medical_classifier import classify_rule_based
from followup_rewriter import is_followup, rewrite_followup
from conversation_context import name_for_key
from symptom_matcher import match_symptoms


def run_turn(query: str, ctx: dict) -> dict:
    """한 턴 처리(오프라인). ctx는 멀티턴 상태({last_symptom_keys, turn_count}).

    멀티턴: 직전 주제가 있고 현재 발화가 후속질의면 검색 질의를 재작성한다.
    안전(§6-1): 현재 발화가 emergency/crisis면 재작성하지 않고 원본으로 처리.
    """
    cls = classify_rule_based(query)
    intent = cls.get("intent")
    cur_keys = match_symptoms(query)

    retrieval_query, method = query, "none"
    if (intent not in ("emergency", "mental_health_crisis")
            and is_followup(query, ctx.get("turn_count", 0), cur_keys)):
        last_keys = ctx.get("last_symptom_keys") or []
        last_name = name_for_key(last_keys[0]) if last_keys else ""
        retrieval_query, method = rewrite_followup(query, last_name)

    res = process_medical_query(retrieval_query)

    # 컨텍스트 갱신: 이번 턴 증상키(없으면 직전 주제 carry-forward)
    new_keys = res["triage"]["symptom_keys"] or cur_keys or ctx.get("last_symptom_keys", [])
    ctx["last_symptom_keys"] = new_keys
    ctx["turn_count"] = ctx.get("turn_count", 0) + 1

    return {"query": query, "retrieval_query": retrieval_query,
            "rewrite_method": method, "result": res}


def print_turn(turn: dict, as_json: bool = False):
    if as_json:
        print(json.dumps(turn, ensure_ascii=False, indent=2))
        return
    r = turn["result"]
    cls = r["classification"]
    print("─" * 64)
    print(f"질문      : {turn['query']}")
    if turn["rewrite_method"] != "none":
        print(f"멀티턴↻   : '{turn['retrieval_query']}' (재작성:{turn['rewrite_method']})")
    print(f"의도/위험 : {cls['intent']} / {cls['risk_level']}")
    print(f"안전분기  : {r['safety_level']}")
    depts = r["triage"]["departments"]
    if depts:
        print(f"진료과    : {', '.join(depts)}")
    flags = cls.get("red_flags") or []
    if flags:
        print(f"레드플래그: {', '.join(str(f) for f in flags)}")
    cov = r["citation"].get("citation_coverage")
    print(f"인용커버  : {cov}")
    print(f"답변      : {r['answer']}")


_EXAMPLES = [
    "배가 아파요", "숨을 못 쉬겠어요", "죽고 싶어요",
    "타이레놀 먹어도 돼요?", "독감 예방접종 언제 맞아요?",
]


def repl():
    ctx = {"last_symptom_keys": [], "turn_count": 0}
    print("RAG 오프라인 테스트 (대화형). 질문을 입력하세요. 종료: 'exit' / 빈 줄.")
    print(f"예시: {', '.join(_EXAMPLES[:3])} …\n")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q or q.lower() in ("exit", "quit", "q"):
            break
        print_turn(run_turn(q, ctx))


def main():
    # .env 시크릿 주입 — 스크립트 실행 시에만(테스트가 run_turn을 import할 때 누출 방지)
    try:
        from env_loader import load_env
        load_env()
    except Exception:
        pass
    args = [a for a in sys.argv[1:]]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if not args:
        repl()
        return
    if args[0] == "--examples":
        ctx = {"last_symptom_keys": [], "turn_count": 0}
        for q in _EXAMPLES:
            print_turn(run_turn(q, ctx), as_json=as_json)
        return
    ctx = {"last_symptom_keys": [], "turn_count": 0}
    print_turn(run_turn(" ".join(args), ctx), as_json=as_json)


if __name__ == "__main__":
    main()
