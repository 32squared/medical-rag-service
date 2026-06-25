"""test_bff_app.py — P0 BFF end-to-end (FastAPI TestClient).

본인인증→계정→세션→동의→채팅 게이트 전 경로 + 보안 불변(토큰·세션철회·중복가입·
동의철회→개인화차단)을 검증. RAG 호출은 모킹(네트워크 분리). DB=임시 SQLite.
"""
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


def _rows(db_file, sql, args=()):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


@pytest.fixture
def bff(tmp_path, monkeypatch):
    db_file = str(tmp_path / "bff.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BFF_TOKEN_SECRET", "test-secret")
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)   # 시설=데모(네트워크 호출 금지)
    import dbcommon as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "_use_postgres", False)
    _apply_sqlite_migrations(db_file)
    import consent_db
    import account_db
    import rag_db
    monkeypatch.setattr(consent_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(account_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(rag_db, "_COACHING_SCHEMA_ENSURED", False)
    monkeypatch.setattr(rag_db, "_CHAT_SCHEMA_ENSURED", False)
    import bff.rag_client as rc
    monkeypatch.setattr(rc, "chat", lambda message, **kw: {"echo": message, "kw": kw})
    from fastapi.testclient import TestClient
    from bff.app import create_app
    return TestClient(create_app()), db_file


def _login(client, identity="010-1111-2222"):
    tx = client.post("/auth/pass/start", json={}).json()["tx_id"]
    return client.post("/auth/pass/callback", json={"tx_id": tx, "mock_identity": identity}).json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_full_flow_and_personalization_gate(bff):
    client, db = bff
    tok = _login(client)
    assert tok["access_token"] and tok["subject_id"]

    me = client.get("/me", headers=_auth(tok)).json()
    assert me["status"] == "active"
    assert me["missing_required"] == ["personal_info"]            # 필수 미동의

    # 필수 동의 → 채팅 가능(개인화는 아직 off: 민감 미동의)
    assert client.post("/consent", headers=_auth(tok),
                       json={"item_key": "personal_info", "action": "grant"}).status_code == 200
    assert client.get("/me", headers=_auth(tok)).json()["missing_required"] == []
    r = client.post("/chat", headers=_auth(tok), json={"message": "두통이 있어요"})
    assert r.status_code == 200 and r.json()["personalization"] is False

    # 민감 동의 → 개인화 on
    client.post("/consent", headers=_auth(tok), json={"item_key": "sensitive_info", "action": "grant"})
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).json()["personalization"] is True

    # 국외 LLM 경로면 cross_border 동의까지 필요
    assert client.post("/chat", headers=_auth(tok),
                       json={"message": "x", "cross_border": True}).json()["personalization"] is False
    client.post("/consent", headers=_auth(tok), json={"item_key": "cross_border", "action": "grant"})
    assert client.post("/chat", headers=_auth(tok),
                       json={"message": "x", "cross_border": True}).json()["personalization"] is True

    # 비식별 동의 이벤트 적재 확인
    ev = _rows(db, "SELECT * FROM analytics_events WHERE event_name='consent_granted'")
    assert ev and {e["consent_item"] for e in ev} >= {"personal_info", "sensitive_info", "cross_border"}


def test_chat_requires_personal_info(bff):
    client, _ = bff
    tok = _login(client)
    r = client.post("/chat", headers=_auth(tok), json={"message": "x"})
    assert r.status_code == 403


def test_no_or_invalid_token_rejected(bff):
    client, _ = bff
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_logout_invalidates_access(bff):
    client, _ = bff
    tok = _login(client)
    client.post("/consent", headers=_auth(tok), json={"item_key": "personal_info", "action": "grant"})
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).status_code == 200
    assert client.post("/auth/logout", headers=_auth(tok)).status_code == 200
    # 같은 access 토큰이 세션 철회로 즉시 무효
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).status_code == 401


def test_duplicate_ci_same_account(bff):
    client, _ = bff
    a = _login(client, identity="same-person")
    b = _login(client, identity="same-person")
    c = _login(client, identity="other-person")
    assert a["subject_id"] == b["subject_id"]      # 중복가입 식별
    assert c["subject_id"] != a["subject_id"]


def test_revoke_consent_blocks_personalization(bff):
    client, _ = bff
    tok = _login(client)
    for item in ("personal_info", "sensitive_info"):
        client.post("/consent", headers=_auth(tok), json={"item_key": item, "action": "grant"})
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).json()["personalization"] is True
    client.post("/consent", headers=_auth(tok), json={"item_key": "sensitive_info", "action": "revoke"})
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).json()["personalization"] is False


def test_consent_history_append_only(bff):
    client, _ = bff
    tok = _login(client)
    client.post("/consent", headers=_auth(tok), json={"item_key": "location", "action": "grant"})
    client.post("/consent", headers=_auth(tok), json={"item_key": "location", "action": "revoke"})
    h = client.get("/consent/history?item_key=location", headers=_auth(tok)).json()["history"]
    assert [r["action"] for r in h] == ["grant", "revoke"]


def test_refresh_rotates_and_old_token_dies(bff):
    client, _ = bff
    tok = _login(client)
    rr = client.post("/auth/refresh",
                     json={"session_id": tok["session_id"], "refresh_token": tok["refresh_token"]})
    assert rr.status_code == 200
    body = rr.json()
    assert body["access_token"]
    assert body["refresh_token"] and body["refresh_token"] != tok["refresh_token"]   # 회전됨
    assert client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200
    # 이전 refresh 재사용 차단(1회용)
    assert client.post("/auth/refresh",
                       json={"session_id": tok["session_id"], "refresh_token": tok["refresh_token"]}).status_code == 401
    # 새 refresh 는 작동
    assert client.post("/auth/refresh",
                       json={"session_id": tok["session_id"], "refresh_token": body["refresh_token"]}).status_code == 200
    # 잘못된 refresh 는 거부
    assert client.post("/auth/refresh",
                       json={"session_id": tok["session_id"], "refresh_token": "wrong"}).status_code == 401


def test_chat_cross_border_ack_gated_by_consent(bff):
    client, _ = bff
    tok = _login(client)
    for item in ("personal_info", "sensitive_info"):
        client.post("/consent", headers=_auth(tok), json={"item_key": item, "action": "grant"})
    # cross_border 동의 없음 → 클라가 cross_border=true 보내도 ack False(국외경로 신호 차단)
    r = client.post("/chat", headers=_auth(tok), json={"message": "x", "cross_border": True})
    assert r.json()["rag"]["kw"]["cross_border_ack"] is False
    client.post("/consent", headers=_auth(tok), json={"item_key": "cross_border", "action": "grant"})
    r = client.post("/chat", headers=_auth(tok), json={"message": "x", "cross_border": True})
    assert r.json()["rag"]["kw"]["cross_border_ack"] is True


def test_relogin_after_withdraw_requires_reconsent(bff):
    client, _ = bff
    tok = _login(client, identity="p1")
    for item in ("personal_info", "sensitive_info"):
        client.post("/consent", headers=_auth(tok), json={"item_key": item, "action": "grant"})
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).json()["personalization"] is True
    assert client.delete("/me", headers=_auth(tok)).status_code == 200
    # 재로그인(같은 신원) → 계정 재활성이되 이전 동의 철회(재동의 필요)
    tok2 = _login(client, identity="p1")
    assert tok2["subject_id"] == tok["subject_id"]
    me = client.get("/me", headers=_auth(tok2)).json()
    assert me["status"] == "active"
    assert "personal_info" in me["missing_required"]                    # 동의 초기화됨
    assert client.post("/chat", headers=_auth(tok2), json={"message": "x"}).status_code == 403


def test_blank_ci_rejected(bff, monkeypatch):
    client, _ = bff
    import bff.pass_adapter as pa
    monkeypatch.setattr(pa, "verify", lambda tx_id, **kw: {"ci": "  ", "di": "x"})
    tx = client.post("/auth/pass/start", json={}).json()["tx_id"]
    assert client.post("/auth/pass/callback", json={"tx_id": tx}).status_code == 400


def test_withdraw_revokes_sessions(bff):
    client, _ = bff
    tok = _login(client)
    client.post("/consent", headers=_auth(tok), json={"item_key": "personal_info", "action": "grant"})
    assert client.delete("/me", headers=_auth(tok)).status_code == 200
    assert client.post("/chat", headers=_auth(tok), json={"message": "x"}).status_code == 401


def test_coaching_config_lists_tracks(bff):
    client, _ = bff
    cfg = client.get("/coaching/config").json()
    keys = {t["key"] for t in cfg["tracks"]}
    assert {"diet", "exercise", "habit"} <= keys
    assert len(next(t for t in cfg["tracks"] if t["key"] == "diet")["intake"]) >= 1


def test_coaching_plan_persists_and_reloads(bff):
    client, _ = bff
    tok = _login(client)
    assert client.get("/coaching", headers=_auth(tok)).json()["plan"] is None       # 처음엔 없음
    r = client.post("/coaching/plan", headers=_auth(tok),
                    json={"track": "diet", "intake": {"eatout": "거의 매일", "salty": "강함", "period": "2주"}})
    assert r.status_code == 200
    pid = r.json()["plan_id"]
    assert pid and r.json()["items"]
    got = client.get("/coaching", headers=_auth(tok)).json()                          # 재조회=재로그인 복원
    assert got["plan"] and got["plan"]["plan_id"] == pid
    key = got["plan"]["items"][0]["key"]
    assert client.post("/coaching/checkin", headers=_auth(tok),
                       json={"plan_id": pid, "item_key": key, "done": True}).status_code == 200
    after = client.get("/coaching", headers=_auth(tok)).json()                        # 체크인 영속
    assert after["stats"]["done"] >= 1
    assert next(i for i in after["plan"]["items"] if i["key"] == key)["done_today"] is True


def test_coaching_isolated_per_subject(bff):
    client, _ = bff
    a = _login(client, identity="coach-a")
    client.post("/coaching/plan", headers=_auth(a),
                json={"track": "habit", "intake": {"focus": "수면", "reg": "불규칙", "period": "2주"}})
    assert client.get("/coaching", headers=_auth(a)).json()["plan"] is not None
    b = _login(client, identity="coach-b")
    assert client.get("/coaching", headers=_auth(b)).json()["plan"] is None           # 계정별 분리


def test_facilities_returns_items(bff):
    client, _ = bff
    tok = _login(client)
    d = client.post("/facilities", headers=_auth(tok),
                    json={"lat": 37.5, "lon": 127.04, "kind": "pharmacy"}).json()
    assert d["kind"] == "pharmacy" and isinstance(d["items"], list) and len(d["items"]) >= 1
    assert "name" in d["items"][0]


def test_consent_items_public(bff):
    client, _ = bff
    items = client.get("/consent/items").json()["items"]
    keys = {i["item_key"] for i in items}
    assert {"personal_info", "sensitive_info", "cross_border"} <= keys
    assert next(i for i in items if i["item_key"] == "personal_info")["required"] is True


def test_home_persona_anticipatory_and_suggested(bff):
    client, _ = bff
    tok = _login(client)
    # 고혈압 어르신(경고밴드) 선택 → sensitive 자동동의. personal_info 동의(홈 게이트).
    assert client.post("/persona/select", json={"persona_id": "hypertension_senior"},
                       headers=_auth(tok)).status_code == 200
    client.post("/consent", json={"item_key": "personal_info", "action": "grant"}, headers=_auth(tok))
    h = client.get("/home", headers=_auth(tok)).json()
    assert h["persona"]["band"] == "경고"
    assert h["cards"] and h["cards"][0]["kind"] == "must_attend"   # 경고 → 선제 must-attend 카드
    assert h["cards"][0]["referral"] == "hospital"
    assert len(h["suggested"]) >= 2                                # 예상질문 + 태그→주제/기저질환


def test_home_requires_personal_info(bff):
    client, _ = bff
    tok = _login(client)                                            # 동의 전엔 403
    assert client.get("/home", headers=_auth(tok)).status_code == 403


def test_chat_history_persist_and_restore(bff):
    client, _ = bff
    tok = _login(client)
    client.post("/consent", json={"item_key": "personal_info", "action": "grant"}, headers=_auth(tok))
    assert client.get("/chat/history", headers=_auth(tok)).json()["messages"] == []
    client.post("/chat", json={"message": "두통이 있어요"}, headers=_auth(tok))   # rag 모킹: echo=message
    msgs = client.get("/chat/history", headers=_auth(tok)).json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "ai"]
    assert msgs[0]["text"] == "두통이 있어요" and msgs[1]["text"] == "두통이 있어요"
    b = _login(client, identity="hist-b")                            # 계정별 분리
    client.post("/consent", json={"item_key": "personal_info", "action": "grant"}, headers=_auth(b))
    assert client.get("/chat/history", headers=_auth(b)).json()["messages"] == []
