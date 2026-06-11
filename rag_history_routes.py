"""
rag_history_routes.py — Phoenix 대화관리(data_management) 호환 라우트 믹스인.

계약: docs/api/COMPAT-conversations.md (projects는 보류 — 대화 5종만).
  GET    /api/data_management/conversations            목록(필터·정렬·페이지)
  GET    /api/data_management/conversations/search     전문 검색(제목+채팅 본문)
  GET    /api/data_management/conversations/{strid}    상세(+chats)
  PATCH  /api/data_management/conversations/{strid}    수정(title/project_strid)
  DELETE /api/data_management/conversations/{strid}    소프트 삭제(DELETED)

설계:
- additive — 기존 /api/rag/*, /api/service/* 무변경.
- 인증: auth_resolver(신뢰헤더+Bearer). 모든 조회는 user_id 스코프.
- 직렬화는 conversation_serializer(순수 함수)에 위임.
- 선행조건: 마이그레이션 011 (display_status 등 컬럼).
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qs

import dbcommon as db
from rag_routes import RAG_ENABLED
from conversation_serializer import (
    build_snippet,
    conversation_to_dict,
    rag_query_to_chat,
    resolve_sort,
    toast,
)

_CONV_PATH = '/api/data_management/conversations'
_CONV_ITEM_RE = re.compile(r'^/api/data_management/conversations/([^/]+)$')

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
        # projects는 보류 (COMPAT-conversations.md §6) — 명시적 안내
        if path.startswith('/api/data_management/projects'):
            return self._send_json(501, {
                "error": "projects API는 아직 제공되지 않습니다 (보류)",
                "toast": toast("NOT_IMPLEMENTED", "프로젝트 기능 준비 중", "INFO")})
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
