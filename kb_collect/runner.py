"""
kb_collect.runner — 카탈로그 항목을 돌려 KB 에 적재하고 ledger 에 기록한다.

단계(출처마다): 게이트(effective_status) → fetch → 품질 필터(kb_content_filter)
  → 위반 사전검사(collect_public_kb.precheck_violations) → evidence_topic 라벨
  → ingest(kb_ingest.ingest_document: 체크섬이 바뀐 문서만 갱신) → ledger.
출처 성격(provenance)은 source_trust 등록부와 맞아야 한다(테스트로 고정).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import kb_catalog
from . import fetchers, ledger
from .clients import now_iso

logger = logging.getLogger(__name__)


def run_sources(source_ids: Optional[List[str]] = None, *, dry_run: bool = False,
                max_items: int = 200, only_due: bool = False,
                env: Optional[Dict[str, str]] = None, clients: Optional[Dict] = None,
                ingest_fn=None, record_fn=None) -> Dict:
    """
    Returns {"runs": [{source_id, status, fetched, inserted, updated, skipped_*, errors}], "skipped": [...]}.
    ingest_fn/record_fn 은 테스트용 주입(기본 kb_ingest.ingest_document / ledger.record_run).
    """
    env = os.environ if env is None else env
    clients = clients or {}
    entries = [e for e in kb_catalog.CATALOG if not source_ids or e["id"] in source_ids]
    unknown = sorted(set(source_ids or []) - {e["id"] for e in entries})
    result: Dict = {"runs": [], "skipped": [], "unknown": unknown}

    for entry in entries:
        eff = kb_catalog.effective_status(entry, env)
        if eff != kb_catalog.STATUS_ACTIVE:
            result["skipped"].append({"source_id": entry["id"], "reason": eff,
                                      "needs": kb_catalog._needs(entry, env)})
            continue
        if only_due and not ledger.is_due(entry):
            result["skipped"].append({"source_id": entry["id"], "reason": "not_due"})
            continue
        result["runs"].append(_run_one(entry, dry_run=dry_run, max_items=max_items, env=env,
                                       clients=clients, ingest_fn=ingest_fn, record_fn=record_fn))
    return result


def _run_one(entry: Dict, *, dry_run: bool, max_items: int, env, clients,
             ingest_fn=None, record_fn=None) -> Dict:
    sid = entry["id"]
    started = now_iso()
    stats = {"source_id": sid, "status": "ok", "fetched": 0, "inserted": 0, "updated": 0,
             "skipped_dup": 0, "skipped_quality": 0, "skipped_violation": 0, "errors": []}
    try:
        fetch = fetchers.get(entry["fetcher"])
        items = fetch(entry, max_items, env, clients) or []
    except NotImplementedError as e:
        stats["status"] = "not_implemented"
        stats["errors"].append(str(e))
        items = []
    except Exception as e:  # noqa: BLE001
        stats["status"] = "fetch_error"
        stats["errors"].append(f"{type(e).__name__}: {e}")
        items = []
    stats["fetched"] = len(items)
    if stats["status"] == "ok" and not items:
        stats["status"] = "empty"   # 조용한 0건을 상태로 드러낸다

    if not dry_run and items:
        _ingest_items(entry, items, stats, ingest_fn=ingest_fn)

    finished = now_iso()
    if not dry_run:
        rec = record_fn or ledger.record_run
        try:
            rec(sid, started_at=started, finished_at=finished, status=stats["status"],
                fetched=stats["fetched"], inserted=stats["inserted"], updated=stats["updated"],
                skipped_dup=stats["skipped_dup"], skipped_quality=stats["skipped_quality"],
                skipped_violation=stats["skipped_violation"], errors=stats["errors"])
        except Exception as e:  # noqa: BLE001
            logger.warning("[kb_collect] ledger 기록 실패 %s: %s", sid, e)
    logger.info("[kb_collect] %s %s fetched=%d inserted=%d updated=%d dup=%d quality=%d violation=%d errors=%d",
                sid, stats["status"], stats["fetched"], stats["inserted"], stats["updated"],
                stats["skipped_dup"], stats["skipped_quality"], stats["skipped_violation"], len(stats["errors"]))
    return stats


def _ingest_items(entry: Dict, items: List[Dict], stats: Dict, ingest_fn=None) -> None:
    from kb_content_filter import assess_content
    from collect_public_kb import label_evidence_topic, precheck_violations
    from retrieval_router import evidence_level_for_source
    ingest = ingest_fn
    sid = entry["id"]
    if ingest is None:
        from kb_ingest import ingest_document, seed_kb_sources
        ingest = ingest_document
        try:   # kb_documents.source_id 외래키 — 카탈로그 항목을 kb_sources 에 멱등 등록
            seed_kb_sources([{
                "id": sid, "name": entry.get("institution", sid), "source_type": "public",
                "license": (entry.get("license") or {}).get("type", "unknown"),
                "update_frequency": f"{entry.get('cadence_days', 30)}d", "is_active": 1,
                "created_at": now_iso(),
            }])
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"kb_sources 등록 실패: {e}")
            return
    try:
        ev_level = evidence_level_for_source(sid)
    except Exception:  # noqa: BLE001
        ev_level = "B"
    for it in items:
        title = it.get("title", "")
        md = it.get("content_md", "")
        q = assess_content(it.get("source_url", ""), md)
        if not q["ok"]:
            stats["skipped_quality"] += 1
            continue
        if precheck_violations(md, source_id=sid):
            stats["skipped_violation"] += 1
            continue
        try:
            res = ingest(
                title=title, content_md=md, source_id=sid,
                metadata={"evidence_level": ev_level, "symptom_tags": [], "department": "general"},
                evidence_country=it.get("_evidence_country", "KR"),
                evidence_topic=label_evidence_topic(md, title=title),
                regulatory_korea=(it.get("_evidence_country", "KR") == "KR"),
                upsert=False, status="active",
                source_url=it.get("source_url"), source_fetched_at=it.get("source_fetched_at"),
                source_checksum=it.get("source_checksum"),
                match_url=entry.get("match_url", True),
            )
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"ingest[{title[:40]}]: {e}")
            continue
        st = (res or {}).get("status")
        if st == "skipped":
            stats["skipped_dup"] += 1
        elif st in ("updated", "upserted"):
            stats["updated"] += 1
        else:
            stats["inserted"] += 1
