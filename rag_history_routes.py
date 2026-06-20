"""
rag_history_routes.py — Phoenix 대화관리(data_management) 호환 라우트 믹스인.

계약: docs/api/COMPAT-conversations.md (Conversations_20260608.pdf §1~9 전체).
  GET    /api/data_management/conversations            목록(필터·정렬·페이지)
  GET    /api/data_management/conversations/search     전문 검색(제목+채팅 본문)
  GET    /api/data_management/conversations/{strid}    상세(+chats)
  PATCH  /api/data_management/conversations/{strid}    수정(title/project_strid)
  DELETE /api/data_management/conversations/{strid}    소프트 삭제(DELETED)
  GET    /api/data_management/projects                 프로젝트 목록(§6)
  POST   /api/data_management/projects                 프로젝트 생성(§7)
  PATCH  /api/data_management/projects/{strid}         프로젝트 수정(§8)
  DELETE /api/data_management/projects/{strid}         프로젝트 소프트 삭제(§9)

설계:
- additive — 기존 /api/rag/*, /api/service/* 무변경.
- 인증: auth_resolver(신뢰헤더+Bearer). 모든 조회는 user_id 스코프.
- 직렬화는 conversation_serializer(순수 함수)에 위임.
- 선행조건: 마이그레이션 011 (display_status 등 컬럼).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs

import dbcommon as db
from rag_routes import RAG_ENABLED
from conversation_serializer import (
    build_snippet,
    conversation_to_dict,
    project_to_dict,
    rag_query_to_chat,
    resolve_project_sort,
    resolve_sort,
    toast,
)

_CONV_PATH = '/api/data_management/conversations'
_CONV_ITEM_RE = re.compile(r'^/api/data_management/conversations/([^/]+)$')
_PROJ_PATH = '/api/data_management/projects'
_PROJ_ITEM_RE = re.compile(r'^/api/data_management/projects/([^/]+)$')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

_CONV_COLS = (
    "id, user_id, user_name, title, env, conversation_strid, created_at, updated_at, "
    "display_status, display_type, project_strid, parent_conversation_strid"
)


def _like_op() -> str:
    return "ILIKE" if db._use_postgres else "LIKE"


class HistoryRoutesMixin:
    """Phoenix 호환 /api/data_management/* 디스패처."""

    # ── 공통 가드 ────────────────────────────────────────────
    def _dm_user(self):
        """RAG_ENABLED·trust·인증 통과 시 user dict, 아니면 None(응답 전송 완료)."""
        if not RAG_ENABLED:
            self._send_json(503, {"error": "RAG 비활성", "code": "RAG_DISABLED"})
            return None
        if not self._trust_ok():
            self._send_error(403, '인증이 필요합니다 (trust secret 불일치)')
            return None
        try:
            from auth_resolver import resolve_user
            user = resolve_user(self.headers)
        except Exception:
            user = self._get_tester_info()
        if not user:
            self._send_error(403, '인증이 필요합니다 (신뢰헤더 또는 Bearer 토큰)')
            return None
        return user

    def _handle_dm_route(self, method, path, parsed, body):
        if path == _CONV_PATH + '/search' and method == 'GET':
            return self._dm_search_conversations(parsed)
        if path == _CONV_PATH and method == 'GET':
            return self._dm_list_conversations(parsed)
        m = _CONV_ITEM_RE.match(path)
        if m:
            strid = m.group(1)
            if method == 'GET':
                return self._dm_get_conversation(strid)
            if method == 'PATCH':
                return self._dm_update_conversation(strid, body)
            if method == 'DELETE':
                return self._dm_delete_conversation(strid)
            return self._send_error(405, 'Method Not Allowed')
        # Projects API (Conversations PDF §6~9)
        if path == _PROJ_PATH:
            if method == 'GET':
                return self._dm_list_projects(parsed)
            if method == 'POST':
                return self._dm_create_project(body)
            return self._send_error(405, 'Method Not Allowed')
        mp = _PROJ_ITEM_RE.match(path)
        if mp:
            pid = mp.group(1)
            if method == 'PATCH':
                return self._dm_update_project(pid, body)
            if method == 'DELETE':
                return self._dm_delete_project(pid)
            return self._send_error(405, 'Method Not Allowed')
        return self._send_error(404, 'Not Found')

    # ── 1. 목록 ──────────────────────────────────────────────
    def _dm_list_conversations(self, parsed):
        user = self._dm_user()
        if not user:
            return
        qs = parse_qs(parsed.query or "")
        project = (qs.get('project_strid', [None])[0])
        start_index = max(0, int(qs.get('start_index', ['0'])[0] or 0))
        limit_raw = qs.get('limit', [None])[0]
        limit = max(1, int(limit_raw)) if limit_raw else 100000
        sort_by = qs.get('sort_by', ['last_used_time'])[0]
        ascending = (qs.get('ascending', ['false'])[0] or '').lower() == 'true'
        order = resolve_sort(sort_by, ascending)

        where = f"user_id = {db._p()} AND COALESCE(display_status,'ACTIVE') = 'ACTIVE'"
        params = [user['id']]
        if project is not None:
            if project == 'null':
                where += " AND project_strid IS NULL"
            else:
                where += f" AND project_strid = {db._p()}"
                params.append(project)

        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM conversations WHERE {where}",
                    tuple(params))
                row = cur.fetchone()
                total = int((dict(row) if hasattr(row, 'keys') else {"cnt": row[0]})["cnt"])

                cur.execute(
                    f"SELECT {_CONV_COLS}, "
                    f"(SELECT COUNT(*) FROM rag_queries q WHERE q.conversation_id = conversations.id) AS num_chats, "
                    f"(SELECT q.query_text FROM rag_queries q WHERE q.conversation_id = conversations.id "
                    f" ORDER BY q.created_at DESC LIMIT 1) AS last_query "
                    f"FROM conversations WHERE {where} "
                    f"ORDER BY {order} LIMIT {db._p()} OFFSET {db._p()}",
                    tuple(params + [limit, start_index]))
                rows = [dict(r) if hasattr(r, 'keys') else r for r in cur.fetchall()]
            results = [
                conversation_to_dict(r, num_chats=r.get("num_chats", 0),
                                     last_query=r.get("last_query") or "", chats=None)
                for r in rows
            ]
            return self._send_json(200, {"results": results, "total_count": total, "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 목록 오류: {e}")
            return self._send_json(500, {
                "results": [], "total_count": 0,
                "toast": toast("INTERNAL_ERROR", "대화 목록 조회 실패 (마이그레이션 011 적용 여부 확인)")})

    # ── 2. 검색 ──────────────────────────────────────────────
    def _dm_search_conversations(self, parsed):
        user = self._dm_user()
        if not user:
            return
        qs = parse_qs(parsed.query or "")
        search_query = (qs.get('search_query', [''])[0] or '').strip()
        if not search_query:
            return self._send_json(400, {
                "results": [], "total_count": 0,
                "toast": toast("BAD_REQUEST", "search_query is required")})
        start_index = max(0, int(qs.get('start_index', ['0'])[0] or 0))
        limit = max(1, int(qs.get('limit', ['10'])[0] or 10))
        dedup = (qs.get('deduplicate', ['false'])[0] or '').lower() == 'true'

        like = _like_op()
        pat = f"%{search_query}%"
        matches = []  # (time, conv_row, chat_strid, snippet_src)
        try:
            with db.get_conn() as (conn, cur):
                # (a) 제목 매칭
                cur.execute(
                    f"SELECT {_CONV_COLS} FROM conversations "
                    f"WHERE user_id = {db._p()} AND COALESCE(display_status,'ACTIVE')='ACTIVE' "
                    f"AND title {like} {db._p()}",
                    (user['id'], pat))
                for r in cur.fetchall():
                    rd = dict(r) if hasattr(r, 'keys') else r
                    matches.append((str(rd.get("created_at") or ""), rd, None,
                                    rd.get("title") or ""))
                # (b) 채팅 본문 매칭 (질의+응답)
                cur.execute(
                    f"SELECT q.id AS chat_id, q.query_text, q.response_text, "
                    f"q.created_at AS chat_time, {', '.join('c.' + c.strip() for c in _CONV_COLS.split(','))} "
                    f"FROM rag_queries q JOIN conversations c ON q.conversation_id = c.id "
                    f"WHERE c.user_id = {db._p()} AND COALESCE(c.display_status,'ACTIVE')='ACTIVE' "
                    f"AND (q.query_text {like} {db._p()} OR q.response_text {like} {db._p()})",
                    (user['id'], pat, pat))
                for r in cur.fetchall():
                    rd = dict(r) if hasattr(r, 'keys') else r
                    text = rd.get("query_text") or ""
                    if search_query.lower() not in text.lower():
                        text = rd.get("response_text") or ""
                    matches.append((str(rd.get("chat_time") or ""), rd,
                                    rd.get("chat_id"), text))
        except Exception as e:
            self._add_log(f"[DM] 검색 오류: {e}")
            return self._send_json(500, {
                "results": [], "total_count": 0,
                "toast": toast("INTERNAL_ERROR", "검색 실패")})

        matches.sort(key=lambda m: m[0], reverse=True)
        if dedup:
            seen, unique = set(), []
            for m in matches:
                key = m[1].get("conversation_strid") or m[1].get("id")
                if key not in seen:
                    seen.add(key)
                    unique.append(m)
            matches = unique

        total = len(matches)
        page = matches[start_index:start_index + limit]
        results = [{
            "conversation": conversation_to_dict(rd, chats=None),
            "chat_strid": chat_id,
            "time": str(t),
            "snippet": build_snippet(text, search_query),
        } for (t, rd, chat_id, text) in page]
        return self._send_json(200, {"results": results, "total_count": total, "toast": None})

    # ── 3. 상세 (+chats) ─────────────────────────────────────
    def _dm_get_conversation(self, strid):
        user = self._dm_user()
        if not user:
            return
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"SELECT {_CONV_COLS} FROM conversations "
                    f"WHERE (conversation_strid = {db._p()} OR id = {db._p()}) "
                    f"AND user_id = {db._p()} AND COALESCE(display_status,'ACTIVE') != 'DELETED'",
                    (strid, strid, user['id']))
                row = cur.fetchone()
                if not row:
                    return self._send_json(404, {
                        "toast": toast("NOT_FOUND_CONVERSATION", "대화를 찾을 수 없습니다")})
                rd = dict(row) if hasattr(row, 'keys') else row
                cur.execute(
                    f"SELECT id, query_text, response_text, citations_json, created_at "
                    f"FROM rag_queries WHERE conversation_id = {db._p()} ORDER BY created_at ASC",
                    (rd.get("id"),))
                chat_rows = [dict(r) if hasattr(r, 'keys') else r for r in cur.fetchall()]
            chats = [rag_query_to_chat(r) for r in chat_rows]
            last_query = chat_rows[-1].get("query_text") if chat_rows else ""
            conv = conversation_to_dict(rd, num_chats=len(chats),
                                        last_query=last_query or "", chats=chats)
            conv["toast"] = None
            return self._send_json(200, conv)
        except Exception as e:
            self._add_log(f"[DM] 상세 오류: {e}")
            return self._send_json(500, {"toast": toast("INTERNAL_ERROR", "대화 조회 실패")})

    # ── 4. 수정 ──────────────────────────────────────────────
    def _dm_update_conversation(self, strid, body):
        user = self._dm_user()
        if not user:
            return
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
        except Exception as e:
            return self._send_json(400, {"status": "error",
                                         "toast": toast("BAD_REQUEST", f"Invalid JSON: {e}")})
        sets, params = [], []
        if 'title' in payload:
            sets.append(f"title = {db._p()}")
            params.append(payload['title'])
        if 'project_strid' in payload:
            sets.append(f"project_strid = {db._p()}")
            params.append(payload['project_strid'])
        if not sets:
            return self._send_json(400, {"status": "error",
                                         "toast": toast("BAD_REQUEST", "수정할 필드가 없습니다")})
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"UPDATE conversations SET {', '.join(sets)} "
                    f"WHERE (conversation_strid = {db._p()} OR id = {db._p()}) AND user_id = {db._p()}",
                    tuple(params + [strid, strid, user['id']]))
                updated = cur.rowcount
                conn.commit()
            if not updated:
                return self._send_json(404, {
                    "status": "error",
                    "toast": toast("NOT_FOUND_CONVERSATION", "대화를 찾을 수 없습니다")})
            return self._send_json(200, {"status": "success", "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 수정 오류: {e}")
            return self._send_json(500, {"status": "error",
                                         "toast": toast("INTERNAL_ERROR", "수정 실패")})

    # ── 5. 삭제 (소프트) ─────────────────────────────────────
    def _dm_delete_conversation(self, strid):
        user = self._dm_user()
        if not user:
            return
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"UPDATE conversations SET display_status = 'DELETED' "
                    f"WHERE (conversation_strid = {db._p()} OR id = {db._p()}) AND user_id = {db._p()}",
                    (strid, strid, user['id']))
                deleted = cur.rowcount
                conn.commit()
            if not deleted:
                return self._send_json(404, {
                    "status": "error",
                    "toast": toast("NOT_FOUND_CONVERSATION", "대화를 찾을 수 없습니다")})
            return self._send_json(200, {"status": "success", "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 삭제 오류: {e}")
            return self._send_json(500, {"status": "error",
                                         "toast": toast("INTERNAL_ERROR", "삭제 실패")})

    # ── 6. 프로젝트 목록 (Conversations PDF §6) ───────────────
    def _dm_list_projects(self, parsed):
        user = self._dm_user()
        if not user:
            return
        qs = parse_qs(parsed.query or "")
        start_index = max(0, int(qs.get('start_index', ['0'])[0] or 0))
        limit_raw = qs.get('limit', [None])[0]
        limit = max(1, int(limit_raw)) if limit_raw else 100000
        sort_by = qs.get('sort_by', ['creation_time'])[0]
        ascending = (qs.get('ascending', ['false'])[0] or '').lower() == 'true'
        order = resolve_project_sort(sort_by, ascending)
        try:
            where = f"user_id = {db._p()} AND COALESCE(display_status,'ACTIVE') = 'ACTIVE'"
            with db.get_conn() as (conn, cur):
                cur.execute(f"SELECT COUNT(*) AS cnt FROM rag_projects WHERE {where}",
                            (user['id'],))
                row = cur.fetchone()
                total = int((dict(row) if hasattr(row, 'keys') else {"cnt": row[0]})["cnt"])
                cur.execute(
                    f"SELECT strid, user_id, name, display_status, creation_time, last_modified_time "
                    f"FROM rag_projects WHERE {where} "
                    f"ORDER BY {order} LIMIT {db._p()} OFFSET {db._p()}",
                    (user['id'], limit, start_index))
                rows = [dict(r) if hasattr(r, 'keys') else r for r in cur.fetchall()]
            results = [project_to_dict(r) for r in rows]
            return self._send_json(200, {"results": results, "total_count": total, "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 프로젝트 목록 오류: {e}")
            return self._send_json(500, {
                "results": [], "total_count": 0,
                "toast": toast("INTERNAL_ERROR", "프로젝트 목록 조회 실패 (마이그레이션 014 적용 여부 확인)")})

    # ── 7. 프로젝트 생성 (Conversations PDF §7) ───────────────
    def _dm_create_project(self, body):
        user = self._dm_user()
        if not user:
            return
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
        except Exception as e:
            return self._send_json(400, {"toast": toast("BAD_REQUEST", f"Invalid JSON: {e}")})
        name = (payload.get('name') or '').strip()
        if not name:
            return self._send_json(400, {"toast": toast("BAD_REQUEST", "name is required")})
        strid = str(uuid.uuid4())
        now = _now_iso()
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"INSERT INTO rag_projects "
                    f"(strid, user_id, name, display_status, creation_time, last_modified_time) "
                    f"VALUES ({db._ph(6)})",
                    (strid, user['id'], name, 'ACTIVE', now, now))
                conn.commit()
            proj = project_to_dict({
                "strid": strid, "user_id": user['id'], "name": name,
                "display_status": "ACTIVE", "creation_time": now, "last_modified_time": now})
            proj["toast"] = None
            return self._send_json(200, proj)
        except Exception as e:
            self._add_log(f"[DM] 프로젝트 생성 오류: {e}")
            return self._send_json(500, {"toast": toast("INTERNAL_ERROR", "프로젝트 생성 실패")})

    # ── 8. 프로젝트 수정 (Conversations PDF §8) ───────────────
    def _dm_update_project(self, strid, body):
        user = self._dm_user()
        if not user:
            return
        try:
            payload = json.loads(body.decode('utf-8')) if body else {}
        except Exception as e:
            return self._send_json(400, {"status": "error",
                                         "toast": toast("BAD_REQUEST", f"Invalid JSON: {e}")})
        name = (payload.get('name') or '').strip()
        if not name:
            return self._send_json(400, {"status": "error",
                                         "toast": toast("BAD_REQUEST", "name is required")})
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"UPDATE rag_projects SET name = {db._p()}, last_modified_time = {db._p()} "
                    f"WHERE strid = {db._p()} AND user_id = {db._p()}",
                    (name, _now_iso(), strid, user['id']))
                updated = cur.rowcount
                conn.commit()
            if not updated:
                return self._send_json(404, {
                    "status": "error",
                    "toast": toast("NOT_FOUND_PROJECT", "프로젝트를 찾을 수 없습니다")})
            return self._send_json(200, {"status": "success", "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 프로젝트 수정 오류: {e}")
            return self._send_json(500, {"status": "error",
                                         "toast": toast("INTERNAL_ERROR", "프로젝트 수정 실패")})

    # ── 9. 프로젝트 삭제 (소프트, Conversations PDF §9) ───────
    def _dm_delete_project(self, strid):
        user = self._dm_user()
        if not user:
            return
        try:
            with db.get_conn() as (conn, cur):
                cur.execute(
                    f"UPDATE rag_projects SET display_status = 'DELETED', last_modified_time = {db._p()} "
                    f"WHERE strid = {db._p()} AND user_id = {db._p()}",
                    (_now_iso(), strid, user['id']))
                deleted = cur.rowcount
                conn.commit()
            if not deleted:
                return self._send_json(404, {
                    "status": "error",
                    "toast": toast("NOT_FOUND_PROJECT", "프로젝트를 찾을 수 없습니다")})
            return self._send_json(200, {"status": "success", "toast": None})
        except Exception as e:
            self._add_log(f"[DM] 프로젝트 삭제 오류: {e}")
            return self._send_json(500, {"status": "error",
                                         "toast": toast("INTERNAL_ERROR", "프로젝트 삭제 실패")})
