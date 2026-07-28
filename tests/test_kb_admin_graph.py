"""
tests/test_kb_admin_graph.py — /api/rag/admin/kb-graph 지식그래프 엔드포인트 테스트

옵시디언식 그래프 뷰 데이터(출처·문서·주제 노드/엣지)가 SQLite 모드에서
정확히 집계되는지 검증한다. 임베딩은 OPENAI_API_KEY 없이 None 경로.
"""

import os
import sys
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.pop("DATABASE_URL", None)


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """각 테스트마다 독립 SQLite DB + 전체 sqlite 마이그레이션 적용."""
    db_file = str(tmp_path / "test_app.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ADMIN_SECRET", raising=False)

    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)

    _init_test_db(db_file)
    yield db_file


def _init_test_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    for sql_path in sorted((REPO_ROOT / "migrations").glob("*_sqlite.sql"),
                           key=lambda p: p.name):
        for stmt in sql_path.read_text(encoding="utf-8").split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.upper() in ("BEGIN", "COMMIT"):
                continue
            lines = [l for l in stmt.splitlines()
                     if l.strip() and not l.strip().startswith("--")]
            if not lines:
                continue
            try:
                conn.execute(stmt)
            except Exception:
                pass
    conn.commit()
    conn.close()


class _FakeHandler:
    """AdminRoutesMixin 단독 구동용 — _send_json/_send_error 캡처."""

    def __init__(self, headers=None):
        self.headers = headers or {}
        self.sent = None

    def _send_json(self, code, obj):
        self.sent = (code, obj)

    def _send_error(self, code, msg):
        self.sent = (code, {"error": msg})


def _make_handler(headers=None):
    from admin_routes import AdminRoutesMixin

    class H(_FakeHandler, AdminRoutesMixin):
        pass

    return H(headers)


def _seed_docs():
    """서로 다른 출처·주제의 문서 2건 + draft 1건 적재."""
    from kb_ingest import seed_kb_sources, ingest_document
    seed_kb_sources()
    r1 = ingest_document(
        title="소아 발열 대응 안내",
        content_md="# 소아 발열\n\n38도 이상이면 미온수 마사지를 고려합니다.\n\n## 응급 신호\n처짐·경련 동반 시 응급실.",
        source_id="kmle_seed", metadata={"evidence_level": "A"},
        evidence_topic="fever_pediatric",
    )
    r2 = ingest_document(
        title="고혈압 생활관리",
        content_md="# 고혈압\n\n저염식과 규칙적 운동이 권장됩니다.",
        source_id="hira_kdca", metadata={"evidence_level": "B"},
        evidence_topic="hypertension",
    )
    r3 = ingest_document(
        title="검수 대기 문서",
        content_md="# 초안\n\n아직 검수되지 않은 내용입니다.",
        source_id="internal_md", metadata={},
        evidence_topic="hypertension", status="draft",
    )
    return r1, r2, r3


def _call(handler, qs=""):
    parsed = urlparse("/api/rag/admin/kb-graph" + (("?" + qs) if qs else ""))
    handler._rag_admin_kb_graph(parsed)
    assert handler.sent is not None, "핸들러가 응답을 보내지 않음"
    return handler.sent


def test_graph_nodes_edges_basic():
    _seed_docs()
    code, out = _call(_make_handler())
    assert code == 200
    ids = {x["id"] for x in out["nodes"]}
    types = {x["id"]: x["type"] for x in out["nodes"]}
    # 출처 3(시드) + 문서 3 + 주제 2
    assert out["stats"]["documents"] == 3
    assert out["stats"]["topics"] == 2
    assert out["stats"]["sources"] >= 3
    assert "s:kmle_seed" in ids and "s:hira_kdca" in ids
    assert "t:fever_pediatric" in ids and "t:hypertension" in ids
    doc_nodes = [x for x in out["nodes"] if x["type"] == "document"]
    assert len(doc_nodes) == 3
    # 문서 노드 size = 청크 수(>0), 메타 포함
    for d in doc_nodes:
        assert d["size"] >= 1
        assert d["meta"]["chunks"] == d["size"]
        assert d["meta"]["source_id"]
    # 엣지: 문서→출처 3, 문서→주제 3 (각 문서 1주제)
    kinds = [e["kind"] for e in out["edges"]]
    assert kinds.count("source") == 3
    assert kinds.count("topic") == 3
    # 엣지 양끝이 모두 노드로 존재
    for e in out["edges"]:
        assert e["a"] in ids and e["b"] in ids
        assert types[e["a"]] == "document"


def test_graph_topic_degree_and_source_docs():
    _seed_docs()
    _, out = _call(_make_handler())
    top = {x["id"]: x for x in out["nodes"] if x["type"] == "topic"}
    # hypertension 은 문서 2건(active+draft) 연결
    assert top["t:hypertension"]["size"] == 2
    assert top["t:fever_pediatric"]["size"] == 1
    src = {x["id"]: x for x in out["nodes"] if x["type"] == "source"}
    assert src["s:kmle_seed"]["meta"]["docs"] == 1
    # 빈 출처 카운트(문서 0인 시드 출처 존재 여부와 일치)
    empty = sum(1 for x in src.values() if x["meta"]["docs"] == 0)
    assert out["stats"]["empty_sources"] == empty


def test_graph_status_filter_active():
    _seed_docs()
    _, out = _call(_make_handler(), "status=active")
    doc_nodes = [x for x in out["nodes"] if x["type"] == "document"]
    assert len(doc_nodes) == 2  # draft 제외
    assert all(d["meta"]["status"] == "active" for d in doc_nodes)
    # draft 문서만 연결됐던 주제 카운트도 감소 반영
    top = {x["id"]: x for x in out["nodes"] if x["type"] == "topic"}
    assert top["t:hypertension"]["size"] == 1


def test_graph_admin_secret_required(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    code, out = _call(_make_handler({"X-Admin-Secret": "wrong"}))
    assert code == 403
    h = _make_handler({"X-Admin-Secret": "s3cret"})
    code2, out2 = _call(h)
    assert code2 == 200 and "nodes" in out2


def test_graph_empty_db():
    """문서 0이어도 200 + 시드 출처 노드만 반환(고아 출처 표시)."""
    from kb_ingest import seed_kb_sources
    seed_kb_sources()
    code, out = _call(_make_handler())
    assert code == 200
    assert out["stats"]["documents"] == 0
    assert out["stats"]["empty_sources"] == out["stats"]["sources"] >= 3
    assert all(x["type"] == "source" for x in out["nodes"])
    assert out["edges"] == []
