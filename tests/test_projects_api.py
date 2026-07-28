"""
Projects API 호환 테스트 (Conversations_20260608.pdf §6~9).

실제 핸들러(HistoryRoutesMixin)를 임시 SQLite로 end-to-end 검증한다
(인증/HTTP 레이어는 stub, DB·직렬화·라우팅 로직은 실제).
"""

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


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
                pass
    conn.commit()
    conn.close()


class _FakeHandler:
    """HistoryRoutesMixin의 HTTP/인증 의존을 stub한 테스트 핸들러."""
    def __init__(self, user):
        self._user = user
        self.responses = []

    def _dm_user(self):
        return self._user

    def _send_json(self, code, payload):
        self.responses.append((code, payload))
        return (code, payload)

    def _send_error(self, code, msg):
        self.responses.append((code, {"error": msg}))
        return (code, {"error": msg})

    def _add_log(self, m):
        pass

    @property
    def last(self):
        return self.responses[-1]


class _Parsed:
    def __init__(self, query=""):
        self.query = query


def _make_handler(user):
    from rag_history_routes import HistoryRoutesMixin

    class H(_FakeHandler, HistoryRoutesMixin):
        pass
    return H(user)


@pytest.fixture
def db_ready(tmp_path, monkeypatch):
    db_file = str(tmp_path / "proj.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", db_file)
    monkeypatch.setattr(dbmod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    return db_file


def test_project_crud_roundtrip(db_ready):
    h = _make_handler({"id": "u1", "name": "U1"})

    # 생성 (§7)
    h._dm_create_project(json.dumps({"name": "프로젝트A"}).encode("utf-8"))
    code, proj = h.last
    assert code == 200 and proj["name"] == "프로젝트A"
    assert proj["display_status"] == "ACTIVE" and proj["user_strid"] == "u1"
    strid = proj["strid"]

    # 목록 (§6)
    h._dm_list_projects(_Parsed(""))
    code, lst = h.last
    assert code == 200 and lst["total_count"] == 1
    assert lst["results"][0]["strid"] == strid

    # 수정 (§8)
    h._dm_update_project(strid, json.dumps({"name": "프로젝트B"}).encode("utf-8"))
    code, upd = h.last
    assert code == 200 and upd["status"] == "success"
    h._dm_list_projects(_Parsed(""))
    assert h.last[1]["results"][0]["name"] == "프로젝트B"

    # 삭제 (§9, 소프트)
    h._dm_delete_project(strid)
    code, dele = h.last
    assert code == 200 and dele["status"] == "success"
    h._dm_list_projects(_Parsed(""))
    assert h.last[1]["total_count"] == 0   # ACTIVE만 노출


def test_create_requires_name(db_ready):
    h = _make_handler({"id": "u1"})
    h._dm_create_project(json.dumps({}).encode("utf-8"))
    code, r = h.last
    assert code == 400


def test_update_nonexistent_returns_404(db_ready):
    h = _make_handler({"id": "u1"})
    h._dm_update_project("no-such", json.dumps({"name": "x"}).encode("utf-8"))
    assert h.last[0] == 404


def test_project_sort_is_whitelisted():
    """정렬 파라미터는 화이트리스트 컬럼만 — SQL 인젝션 차단."""
    from conversation_serializer import resolve_project_sort
    assert resolve_project_sort("name", True) == "name ASC"
    assert resolve_project_sort("last_modified_time", False) == "last_modified_time DESC"
    # 미허용/악의 입력 → 기본 컬럼으로 폴백
    assert resolve_project_sort("name; DROP TABLE rag_projects", False) == "creation_time DESC"
    assert resolve_project_sort(None, False) == "creation_time DESC"


def test_projects_are_user_scoped(db_ready):
    h1 = _make_handler({"id": "u1"})
    h1._dm_create_project(json.dumps({"name": "u1의 프로젝트"}).encode("utf-8"))
    # 다른 사용자는 못 본다
    h2 = _make_handler({"id": "u2"})
    h2._dm_list_projects(_Parsed(""))
    assert h2.last[1]["total_count"] == 0
