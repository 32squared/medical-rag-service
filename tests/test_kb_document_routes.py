"""
KB 문서 조회 라우트 — PostgreSQL 모양(dict 행)·PostgreSQL 스키마 회귀.

2026-09-29 dev(PostgreSQL, medical_app_dev)에서 두 조회가 500 이었다.
  - GET /api/rag/kb/documents : COUNT 행이 dict(RealDictCursor)인데 total_row[0] → KeyError: 0
    ("KB 문서 조회 실패: 0")
  - GET /api/rag/kb/documents/<id> : kb_chunks 에 없는 section_path_json · topic_keywords_json 을 SELECT
    (컬럼은 PostgreSQL·SQLite 모두 section_path · topic_keywords — 마이그레이션 누락이 아니라 이름 오류)
테스트 DB 는 SQLite 이고 sqlite3.Row 는 번호로도 읽혀서 목록 버그를 못 잡았고, 단건 조회는 테스트가 없었다.
여기서는 SQLite 커서를 감싸 PostgreSQL 처럼 dict 행을 돌려주고, 두 라우트가 쓰는 컬럼이
PostgreSQL 마이그레이션(migrations/*.sql, *_sqlite.sql 제외)에 있는지 확인한다.
"""
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NOW = "2026-09-29T00:00:00+00:00"
META = {"symptom_tags": ["fasting_glucose"]}
CHUNKS = [(["공복혈당", "정상"], ["공복혈당"]), (["공복혈당", "당뇨병 의심"], ["당뇨병"])]


def _apply_sqlite_migrations(db_path):
    conn = sqlite3.connect(db_path)
    for f in sorted((REPO_ROOT / "migrations").glob("*_sqlite.sql"), key=lambda p: p.name):
        for stmt in f.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            if not s or s.upper() in ("BEGIN", "COMMIT"):
                continue
            try:
                conn.execute(s)
            except Exception:
                pass  # SQLite ADD COLUMN 은 IF NOT EXISTS 가 없다 — 중복은 무시
    conn.commit()
    conn.close()


def _seed(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO kb_sources (id, name, source_type, license, is_active, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("src_kbdoc", "테스트 출처", "public", "kogl_type1", 1, NOW))
    conn.execute(
        "INSERT INTO kb_documents (id, source_id, title, content_md, metadata_json, status, "
        "evidence_level, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("doc-1", "src_kbdoc", "공복혈당 판정기준", "# 공복혈당", json.dumps(META), "active", "A", 1, NOW, NOW))
    for i, (section_path, keywords) in enumerate(CHUNKS):
        conn.execute(
            "INSERT INTO kb_chunks (id, document_id, chunk_index, content, section_path, "
            "embedding_primary_model, evidence_country, evidence_topic, regulatory_korea, "
            "topic_keywords, token_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"chunk-{i}", "doc-1", i, f"본문 {i}", json.dumps(section_path, ensure_ascii=False),
             "openai_small_v3", "KR", "fasting_glucose", 1, json.dumps(keywords, ensure_ascii=False), 10, NOW))
    conn.commit()
    conn.close()


class _DictRows:
    """sqlite 커서를 감싸 PostgreSQL RealDictCursor 처럼 행을 dict 로 돌려준다(번호로는 못 읽는다)."""

    def __init__(self, cur, log):
        self._cur, self._log = cur, log

    def execute(self, sql, args=()):
        self._log.append(sql)
        self._cur.execute(sql, args)

    def _row(self, r):
        return None if r is None else {d[0]: v for d, v in zip(self._cur.description, r)}

    def fetchone(self):
        return self._row(self._cur.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]


class _Fake:
    def _send_json(self, code, payload):
        return code, payload

    def _send_error(self, code, msg):
        return code, {"error": msg}

    def _add_log(self, m):
        pass


@pytest.fixture
def kb_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "kbdoc.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    _seed(db_file)
    return db_file


def _handler(kb_db, monkeypatch, dict_rows):
    import rag_routes
    monkeypatch.setattr(rag_routes, "RAG_ENABLED", True)
    sql_log = []
    if dict_rows:
        @contextmanager
        def _pg_like_conn(db_path=None):
            conn = sqlite3.connect(kb_db)
            try:
                yield conn, _DictRows(conn.cursor(), sql_log)
                conn.commit()
            finally:
                conn.close()
        monkeypatch.setattr(rag_routes.db, "get_conn", _pg_like_conn)

    class H(_Fake, rag_routes.RagRoutesMixin):
        pass
    h = H()
    h.sql_log = sql_log
    return h


@pytest.fixture(params=["sqlite_row", "dict_row"])
def handler(request, kb_db, monkeypatch):
    return _handler(kb_db, monkeypatch, dict_rows=request.param == "dict_row")


def test_list_documents_by_source(handler):
    code, body = handler._rag_kb_list_documents("source_id=src_kbdoc")
    assert code == 200, body
    assert body["total"] == 1
    [doc] = body["documents"]
    assert doc["id"] == "doc-1"
    assert doc["source_name"] == "테스트 출처"
    assert doc["chunks_count"] == 2
    assert doc["metadata"] == META


def test_list_documents_no_match_total_zero(handler):
    code, body = handler._rag_kb_list_documents("source_id=no_such_source")
    assert code == 200, body
    assert body["total"] == 0
    assert body["documents"] == []


def test_get_document_with_chunks(handler):
    code, body = handler._rag_kb_get_document("doc-1")
    assert code == 200, body
    assert body["title"] == "공복혈당 판정기준"
    assert body["metadata"] == META
    assert body["chunks_count"] == 2
    for chunk, (section_path, keywords) in zip(body["chunks"], CHUNKS):
        assert chunk["section_path"] == section_path
        assert chunk["topic_keywords"] == keywords
        assert chunk["evidence_topic"] == "fasting_glucose"
        assert "section_path_json" not in chunk and "topic_keywords_json" not in chunk


def test_get_document_missing_is_404(handler):
    code, _ = handler._rag_kb_get_document("no-such-doc")
    assert code == 404


# ── PostgreSQL 스키마 대조 ──────────────────────────────────────

def _split_top(text):
    """괄호 밖 쉼표로 나눈다."""
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _pg_schema():
    """PostgreSQL 마이그레이션(*_sqlite.sql 제외)을 파일 순서대로 읽어 테이블 → 컬럼 집합."""
    cols = {}
    for f in sorted((REPO_ROOT / "migrations").glob("*.sql"), key=lambda p: p.name):
        if f.name.endswith("_sqlite.sql"):
            continue
        text = re.sub(r"--[^\n]*", "", f.read_text(encoding="utf-8"))
        for stmt in text.split(";"):
            m = re.match(r"\s*CREATE TABLE (?:IF NOT EXISTS )?(\w+)\s*\((.*)\)\s*$", stmt, re.S | re.I)
            if m:
                table = cols.setdefault(m.group(1).lower(), set())
                for part in _split_top(m.group(2)):
                    name = part.split()[0].strip('"').lower()
                    if name not in ("primary", "foreign", "unique", "constraint", "check", "exclude"):
                        table.add(name)
                continue
            m = re.match(r"\s*ALTER TABLE (?:IF EXISTS )?(?:ONLY )?(\w+)\s+(.*)$", stmt, re.S | re.I)
            if m:
                table = cols.setdefault(m.group(1).lower(), set())
                body = m.group(2)
                table.update(c.lower() for c in re.findall(r"ADD COLUMN (?:IF NOT EXISTS )?(\w+)", body, re.I))
                for old, new in re.findall(r"RENAME COLUMN (\w+) TO (\w+)", body, re.I):
                    table.discard(old.lower())
                    table.add(new.lower())
                table.difference_update(
                    c.lower() for c in re.findall(r"DROP COLUMN (?:IF EXISTS )?(\w+)", body, re.I))
    return cols


_NOT_ALIAS = {"where", "left", "right", "inner", "join", "on", "order", "group", "limit"}


def _referenced_columns(sql):
    """SQL 한 문장이 쓰는 (테이블, 컬럼) — 별칭(d.x) 참조와, 별칭 없는 단일 테이블 SELECT 의 컬럼."""
    aliases = {a.lower(): t.lower()
               for t, a in re.findall(r"\b(?:FROM|JOIN)\s+(\w+)\s+(?:AS\s+)?(\w+)\b", sql, re.I)
               if a.lower() not in _NOT_ALIAS}
    refs = {(aliases[a.lower()], c.lower()) for a, c in re.findall(r"\b(\w+)\.(\w+)\b", sql)
            if a.lower() in aliases}
    m = re.match(r"\s*SELECT\s+(.*?)\s+FROM\s+(\w+)\s+(.*)$", sql, re.S | re.I)
    if m and "." not in m.group(1):
        table = m.group(2).lower()
        names = [re.split(r"\s+AS\s+", item, flags=re.I)[0].strip() for item in _split_top(m.group(1))]
        names += re.findall(r"\b(\w+)\s*(?:=|LIKE)", m.group(3), re.I)
        names += re.findall(r"ORDER BY\s+(\w+)", m.group(3), re.I)
        refs |= {(table, n.lower()) for n in names if re.fullmatch(r"\w+", n)}
    return refs


def test_schema_parser_sees_real_columns():
    schema = _pg_schema()
    assert {"section_path", "topic_keywords", "evidence_topic"} <= schema["kb_chunks"]
    assert "section_path_json" not in schema["kb_chunks"]
    assert "source_url" in schema["kb_documents"]  # 003 ALTER TABLE ADD COLUMN
    assert {("kb_chunks", "section_path_json"), ("kb_chunks", "document_id")} <= _referenced_columns(
        "SELECT id, section_path_json FROM kb_chunks WHERE document_id = %s ORDER BY chunk_index")


def test_kb_document_routes_use_postgres_columns(kb_db, monkeypatch):
    h = _handler(kb_db, monkeypatch, dict_rows=True)
    list_code, _ = h._rag_kb_list_documents(
        "source_id=src_kbdoc&status=active&symptom=fasting&q=%EA%B3%B5%EB%B3%B5")
    get_code, _ = h._rag_kb_get_document("doc-1")

    # 실행이 실패해도 보낸 SQL 은 기록된다 — 없는 컬럼을 먼저 이름으로 보여 준다
    refs = set().union(*(_referenced_columns(sql) for sql in h.sql_log))
    schema = _pg_schema()
    missing = sorted(f"{t}.{c}" for t, c in refs if c not in schema.get(t, set()))
    assert missing == []
    assert {t for t, _ in refs} >= {"kb_documents", "kb_sources", "kb_chunks"}
    assert (list_code, get_code) == (200, 200)
