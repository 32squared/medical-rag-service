"""kb_collect — 파서·OpenAPI 클라이언트(가짜 세션)·runner(주입)·ledger(SQLite)."""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import kb_catalog as kc
from kb_collect import clients, fetchers, parsers
from kb_collect import runner as kr


# ── parsers ─────────────────────────────────────────────────

def test_records_to_documents_keeps_text_and_builds_url():
    recs = [
        {"itemSeq": "1", "itemName": "타이레놀정", "efcyQesitm": "<p>해열&nbsp;진통</p>", "useMethodQesitm": ""},
        {"itemSeq": "2", "itemName": "", "efcyQesitm": "x"},            # 제목 없음 → 제외
        {"itemSeq": "3", "itemName": "빈약", "efcyQesitm": "", "useMethodQesitm": ""},  # 본문 없음 → 제외
    ]
    docs = parsers.records_to_documents(
        recs, title_field="itemName",
        body_fields=[("효능", "efcyQesitm"), ("용법", "useMethodQesitm")],
        url_template="https://nedrug.mfds.go.kr/searchDrug/resultDrugDetail?itemSeq={itemSeq}",
        id_field="itemSeq", institution="식품의약품안전처 e약은요",
    )
    assert len(docs) == 1
    d = docs[0]
    assert d["title"] == "타이레놀정"
    assert "## 효능\n\n해열 진통" in d["content_md"]
    assert "## 용법" not in d["content_md"]
    assert d["source_url"].endswith("itemSeq=1")
    assert len(d["source_checksum"]) == 64 and d["external_id"] == "1"


# ── DataGoKrClient (가짜 세션) ───────────────────────────────

class _Resp:
    def __init__(self, payload, ctype="application/json", status=200):
        self.text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        self.headers = {"Content-Type": ctype}
        self.status_code = status


class _Session:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append(kw.get("params"))
        page = int(kw["params"]["pageNo"])
        return self.pages[page - 1]


def _page(items, total):
    return _Resp({"response": {"header": {"resultCode": "00", "resultMsg": "OK"},
                               "body": {"items": {"item": items}, "totalCount": total}}})


def test_datagokr_client_pages_until_total():
    sess = _Session([_page([{"a": 1}, {"a": 2}], 3), _page([{"a": 3}], 3)])
    c = clients.DataGoKrClient("KEY", session=sess)
    c._rate_sleep = 0
    out = list(c.iter_items("https://apis.data.go.kr/x", page_size=2, max_items=10))
    assert [o["a"] for o in out] == [1, 2, 3]
    assert len(sess.calls) == 2 and sess.calls[0]["serviceKey"] == "KEY"


def test_datagokr_client_raises_on_error_code():
    bad = _Resp({"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED ERROR"},
                              "body": {}}})
    c = clients.DataGoKrClient("KEY", session=_Session([bad]))
    c._rate_sleep = 0
    with pytest.raises(RuntimeError, match="NOT REGISTERED"):
        list(c.iter_items("https://apis.data.go.kr/x"))


def test_datagokr_client_parses_xml():
    xml = ("<response><header><resultCode>00</resultCode></header>"
           "<body><items><item><a>1</a></item><item><a>2</a></item></items><totalCount>2</totalCount></body></response>")
    c = clients.DataGoKrClient("KEY", session=_Session([_Resp(xml, ctype="application/xml")]))
    c._rate_sleep = 0
    out = list(c.iter_items("https://apis.data.go.kr/x"))
    assert [o["a"] for o in out] == ["1", "2"]


def test_datagokr_client_requires_key():
    with pytest.raises(ValueError):
        clients.DataGoKrClient("")


# ── runner (fetcher·ingest·ledger 주입) ─────────────────────

@pytest.fixture
def fake_entry(monkeypatch):
    entry = {
        "id": "mfds_dur", "institution": "식약처", "access": kc.ACCESS_OPENAPI,
        "fetcher": "_fake", "key_env": "DATA_GO_KR_KEY",
        "license": kc._lic("kogl_type1"), "provenance": "institution_verbatim",
        "cadence_days": 30, "status": kc.STATUS_ACTIVE, "match_url": True, "routes": [],
    }
    monkeypatch.setattr(kc, "CATALOG", [entry, dict(entry, id="health_kdca", status=kc.STATUS_PENDING_LICENSE)])
    return entry


def _docs(n):
    body = ("당뇨병은 혈당이 높아지는 만성 질환으로 식사 조절과 운동이 중요합니다. " * 20
            + "\n\n본 정보는 참고용이며 진단·치료는 의사와 상담하십시오.")
    return [{"title": f"문서{i}", "content_md": "# 제목\n\n" + body, "source_url": f"https://x/{i}",
             "source_checksum": "c" * 64, "source_fetched_at": "2026-10-28T00:00:00+00:00"} for i in range(n)]


def test_runner_skips_gated_and_runs_active(fake_entry, monkeypatch):
    fetchers._REGISTRY["_fake"] = lambda entry, n, env, clients: _docs(3)
    calls = []
    recorded = []

    def ingest(**kw):
        calls.append(kw)
        return {"status": "inserted" if len(calls) < 3 else "skipped"}

    res = kr.run_sources(env={"DATA_GO_KR_KEY": "k"}, ingest_fn=ingest,
                         record_fn=lambda sid, **kw: recorded.append((sid, kw)))
    assert [s["source_id"] for s in res["skipped"]] == ["health_kdca"]
    assert res["skipped"][0]["reason"] == kc.STATUS_PENDING_LICENSE
    run = res["runs"][0]
    assert run["status"] == "ok" and run["fetched"] == 3
    assert run["inserted"] == 2 and run["skipped_dup"] == 1
    assert calls[0]["source_id"] == "mfds_dur" and calls[0]["upsert"] is False
    assert recorded and recorded[0][0] == "mfds_dur" and recorded[0][1]["status"] == "ok"


def test_runner_dry_run_does_not_ingest_or_record(fake_entry):
    fetchers._REGISTRY["_fake"] = lambda entry, n, env, clients: _docs(2)
    hits = []
    res = kr.run_sources(["mfds_dur"], dry_run=True, env={"DATA_GO_KR_KEY": "k"},
                         ingest_fn=lambda **kw: hits.append(1), record_fn=lambda *a, **k: hits.append(2))
    assert res["runs"][0]["fetched"] == 2 and hits == []


def test_runner_marks_empty_and_errors(fake_entry):
    fetchers._REGISTRY["_fake"] = lambda entry, n, env, clients: []
    res = kr.run_sources(["mfds_dur"], env={"DATA_GO_KR_KEY": "k"}, ingest_fn=lambda **kw: None,
                         record_fn=lambda *a, **k: None)
    assert res["runs"][0]["status"] == "empty"

    def boom(entry, n, env, clients):
        raise RuntimeError("SERVICE KEY IS NOT REGISTERED")
    fetchers._REGISTRY["_fake"] = boom
    res = kr.run_sources(["mfds_dur"], env={"DATA_GO_KR_KEY": "k"}, ingest_fn=lambda **kw: None,
                         record_fn=lambda *a, **k: None)
    assert res["runs"][0]["status"] == "fetch_error" and "NOT REGISTERED" in res["runs"][0]["errors"][0]


def test_runner_not_implemented_is_visible(fake_entry):
    fetchers._REGISTRY["_fake"] = fetchers._not_implemented("x")
    res = kr.run_sources(["mfds_dur"], env={"DATA_GO_KR_KEY": "k"}, ingest_fn=lambda **kw: None,
                         record_fn=lambda *a, **k: None)
    assert res["runs"][0]["status"] == "not_implemented"


def test_runner_unknown_source_reported(fake_entry):
    res = kr.run_sources(["nope"], env={}, ingest_fn=lambda **kw: None, record_fn=lambda *a, **k: None)
    assert res["unknown"] == ["nope"] and res["runs"] == []


# ── ledger (SQLite) ─────────────────────────────────────────

def _init_sqlite(db_path: str):
    conn = sqlite3.connect(db_path)
    for sql_path in sorted((REPO_ROOT / "migrations").glob("*_sqlite.sql"), key=lambda p: p.name):
        for stmt in sql_path.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            lines = [l for l in s.splitlines() if l.strip() and not l.strip().startswith("--")]
            if not lines or s.upper() in ("BEGIN", "COMMIT"):
                continue
            try:
                conn.execute(s)
            except sqlite3.OperationalError:
                pass  # 중복 컬럼 등 additive 마이그레이션 충돌은 무시
    conn.commit()
    conn.close()


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "t.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", db_file)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _init_sqlite(db_file)
    return db_file


def test_ledger_roundtrip_and_due(sqlite_db):
    from datetime import datetime, timedelta, timezone
    from kb_collect import ledger
    entry = {"id": "mfds_dur", "cadence_days": 30}
    assert ledger.is_due(entry)
    t = datetime.now(timezone.utc)
    ledger.record_run("mfds_dur", started_at=(t - timedelta(minutes=1)).isoformat(),
                      finished_at=t.isoformat(), status="ok", fetched=5, inserted=5)
    assert ledger.last_success("mfds_dur") == t.isoformat()
    assert not ledger.is_due(entry, now=t + timedelta(days=10))
    assert ledger.is_due(entry, now=t + timedelta(days=31))
    runs = ledger.recent_runs()
    assert runs[0]["source_id"] == "mfds_dur" and runs[0]["fetched"] == 5
    # 실패 기록은 last_success 에 영향 없음
    ledger.record_run("mfds_dur", started_at=t.isoformat(), finished_at=(t + timedelta(hours=1)).isoformat(),
                      status="fetch_error", errors=["x"])
    assert ledger.last_success("mfds_dur") == t.isoformat()
