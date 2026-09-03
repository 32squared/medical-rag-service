"""test_metrics_routes.py — 오늘의 나 재미 레이어 BFF 라우트 + 홈 1콜 확장.

정본: docs/design/todays-me-mockups/02-dev-requirements.md §4·§6.
검증 축: 홈 응답 기존 키 불변 + 3블록 추가 / 지표 입력→깨어남·완료→아키타입 / 밴드 게이트 403 /
        동의 게이트 / 화면 2 페이로드·CTA 4변형 / 리빌 seen / 웰니스 타입 문진·변경 / 카드 생성·잠금·검증 /
        응답에 금지 필드 없음 / 계정 격리.
"""
import pathlib
import sqlite3

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


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


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "bff.db")
    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BFF_TOKEN_SECRET", "test-secret")
    monkeypatch.delenv("DATA_GO_KR_KEY", raising=False)
    import dbcommon
    monkeypatch.setattr(dbcommon, "DB_PATH", db)
    monkeypatch.setattr(dbcommon, "_use_postgres", False)
    _apply_sqlite_migrations(db)
    import account_db
    import consent_db
    import rag_db
    import routine_repo
    import metrics_repo
    monkeypatch.setattr(consent_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(account_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(rag_db, "_COACHING_SCHEMA_ENSURED", False)
    monkeypatch.setattr(routine_repo, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(metrics_repo, "_SCHEMA_ENSURED", False)
    from fastapi.testclient import TestClient
    from bff.app import create_app
    return TestClient(create_app())


def _login(c, identity="fun-user", persona="healthy_office", consent=True):
    tx = c.post("/auth/pass/start", json={}).json()["tx_id"]
    tok = c.post("/auth/pass/callback", json={"tx_id": tx, "mock_identity": identity}).json()
    h = {"Authorization": "Bearer " + tok["access_token"]}
    if consent:
        c.post("/consent", json={"item_key": "personal_info", "action": "grant"}, headers=h)
    if persona:
        c.post("/persona/select", json={"persona_id": persona}, headers=h)
    return h


FORBIDDEN_KEYS = ("bp", "glucose", "band_label", "grade", "missed", "rank", "percentile")


def _assert_no_forbidden(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = k.lower()
            assert not any(f in lk for f in FORBIDDEN_KEYS), path + "/" + k
            _assert_no_forbidden(v, path + "/" + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_forbidden(v, f"{path}[{i}]")


# ── 홈 1콜 확장 ─────────────────────────────────────────────
def test_today_gets_fun_blocks_without_breaking_existing_keys(client):
    h = _login(client)
    d = client.get("/routine/today", headers=h).json()
    for k in ("server_date", "band", "safety", "program", "today", "weeks", "week_days", "stats"):
        assert k in d
    assert d["safety"]["fun_layer"] is True
    assert set(d["tracks"]) == {"water", "steps", "mind"}
    assert d["archetype"] == {"preview": None, "completed_count": 0, "seen_today": False}
    assert d["date_kst"] == d["server_date"]


def test_today_warning_band_hides_fun_layer(client):
    h = _login(client, persona="hypertension_senior")          # 경고 밴드
    d = client.get("/routine/today", headers=h).json()
    assert d["safety"]["fun_layer"] is False and d["archetype"] is None
    assert d["tracks"]["water"]["complete"] is False


# ── 지표 입력 → 깨어남·완료 → 아키타입 ───────────────────────
def test_metrics_flow_to_balance_monk(client):
    h = _login(client)
    r = client.put("/metrics/today", json={"water_cups": 1}, headers=h).json()
    assert r["ok"] and r["tracks"]["water"]["awake"] and not r["tracks"]["water"]["complete"]
    assert r["archetype"]["preview"] is None

    r = client.put("/metrics/today", json={"water_cups": 6}, headers=h).json()
    assert r["tracks"]["water"]["complete"] and r["archetype"]["preview"] == "hydration_king"

    r = client.put("/metrics/today", json={"steps": 6400, "steps_source": "manual"}, headers=h).json()
    assert r["archetype"]["preview"] == "sunny_runner" and r["tracks"]["steps"]["stale"] is False

    r = client.put("/metrics/today", json={"mind_session_completed": True}, headers=h).json()
    assert r["archetype"]["preview"] == "balance_monk" and r["archetype"]["completed_count"] == 3
    _assert_no_forbidden(r)

    # 되돌리기(컵 0) → 조합 축소
    r = client.put("/metrics/today", json={"water_cups": 0}, headers=h).json()
    assert r["archetype"]["preview"] == "night_owl_reformed"


def test_metrics_validation(client):
    h = _login(client)
    assert client.put("/metrics/today", json={"water_cups": 9}, headers=h).status_code == 400
    assert client.put("/metrics/today", json={"steps": -1}, headers=h).status_code == 400
    assert client.put("/metrics/today", json={"mind_session_completed": True, "mind_seconds": 30},
                      headers=h).status_code == 400          # 완주만 세션
    assert client.put("/metrics/today", json={"bedtime_at": "nope"}, headers=h).status_code == 400


def test_metrics_requires_personal_consent(client):
    h = _login(client, consent=False)
    assert client.put("/metrics/today", json={"water_cups": 1}, headers=h).status_code == 403


def test_steps_sync_does_not_override_manual_confirmed(client):
    h = _login(client)
    client.put("/metrics/today", json={"steps": 7000, "steps_source": "manual", "steps_confirmed": True}, headers=h)
    r = client.post("/metrics/steps/sync", json={"steps": 100}, headers=h).json()
    assert r["tracks"]["steps"]["value"] == 7000 and r["tracks"]["steps"]["complete"]


# ── 화면 2 ───────────────────────────────────────────────────
def test_metrics_day_payload_and_cta_variants(client):
    h = _login(client)
    d = client.get("/metrics/day", headers=h).json()
    assert d["completed_count"] == 0 and d["cta"] == "go_today" and d["metrics"] == []
    assert d["highlight"]["type"] == "f3"

    client.put("/metrics/today", json={"water_cups": 6, "steps": 6400, "steps_source": "manual",
                                       "mind_session_completed": True, "mind_seconds": 420}, headers=h)
    d = client.get("/metrics/day", headers=h).json()
    assert d["completed_count"] == 3 and d["cta"] == "reveal" and d["is_today"]
    kinds = {m["kind"]: m for m in d["metrics"]}
    assert kinds["water_cups"]["conversion_text"] == "= 작은 화분 3개"
    assert kinds["steps"]["conversion_text"] == "= 한강 다리 2개"
    assert kinds["mindful_min"]["value"] == 7 and kinds["mindful_min"]["conversion_text"] == "= 노래 2곡"
    assert d["highlight"]["type"] == "f1"
    assert "일째" in d["streak_text"] or d["streak_text"] == "기록이 남았어요"
    _assert_no_forbidden(d)

    client.post("/archetype/seen", json={}, headers=h)
    assert client.get("/metrics/day", headers=h).json()["cta"] == "reveal_replay"


def test_metrics_day_warning_band_cta(client):
    h = _login(client, persona="hypertension_senior")
    client.put("/metrics/today", json={"water_cups": 6}, headers=h)
    d = client.get("/metrics/day", headers=h).json()
    assert d["fun_layer"] is False and d["cta"] == "weekly_report" and d["completed_count"] == 0
    assert d["streak_text"] == "오늘 기록이 남았어요" and d["highlight"] is None


# ── 화면 3 ───────────────────────────────────────────────────
def test_archetype_day_and_seen(client):
    h = _login(client)
    assert client.get("/archetype/day", headers=h).status_code == 404      # 0완료
    client.put("/metrics/today", json={"water_cups": 6, "mind_session_completed": True}, headers=h)
    a = client.get("/archetype/day", headers=h).json()
    assert a["archetype_id"] == "zen_barista" and a["name_ko"] == "젠 바리스타"
    assert a["tags"] == ["물 6컵", "마음챙김 1분"]
    assert a["rarity_pct"] is None and a["rarity_text"] is None          # 표본 없음 → 줄 숨김
    assert a["seen_today"] is False
    assert len(a["collection_last7"]) == 1 and a["collection_last7"][0]["is_today"]
    _assert_no_forbidden(a)
    assert client.post("/archetype/seen", json={}, headers=h).json()["ok"]
    assert client.get("/archetype/day", headers=h).json()["seen_today"] is True


def test_archetype_blocked_by_band(client):
    h = _login(client, persona="hypertension_senior")
    client.put("/metrics/today", json={"water_cups": 6}, headers=h)
    assert client.get("/archetype/day", headers=h).status_code == 403
    assert client.post("/card", json={}, headers=h).status_code == 403
    assert client.get("/card/list", headers=h).status_code == 403


# ── 웰니스 타입 ─────────────────────────────────────────────
def test_wellness_type_quiz_and_change(client):
    h = _login(client)
    q = client.get("/wellness-type/quiz", headers=h).json()
    assert len(q["questions"]) == 4 and all(len(x["options"]) == 5 for x in q["questions"])
    assert client.get("/wellness-type", headers=h).json()["type_id"] is None
    r = client.post("/wellness-type/quiz", json={"answers": [0, 4, 0, 4]}, headers=h).json()
    assert r["type_id"] == "baby_godsaeng" and r["assigned_by"] == "onboarding"
    assert client.post("/wellness-type/quiz", json={"answers": [0, 1]}, headers=h).status_code == 400
    r = client.put("/wellness-type", json={"type_id": "ritual_fairy"}, headers=h).json()
    assert r["type_id"] == "ritual_fairy" and r["previous"] == "baby_godsaeng" and r["assigned_by"] == "user"
    assert client.put("/wellness-type", json={"type_id": "zzz"}, headers=h).status_code == 400


# ── 공유 카드 ─────────────────────────────────────────────────
def test_card_create_patch_and_lock(client, monkeypatch):
    h = _login(client)
    assert client.post("/card", json={}, headers=h).status_code == 404          # 아키타입 없음
    client.post("/wellness-type/quiz", json={"answers": [4, 4, 4, 4]}, headers=h)   # 신생아 → coral
    client.put("/metrics/today", json={"water_cups": 6, "steps": 6400, "steps_source": "manual",
                                       "mind_session_completed": True, "mind_seconds": 420}, headers=h)
    c = client.post("/card", json={}, headers=h).json()
    p = c["payload"]
    assert p["archetype_en"] == "Balance Monk" and p["theme_id"] == "coral"
    assert p["wellness_type_label"] == "갓생 신생아 타입" and len(p["metrics"]) == 3
    assert c["locked"] is False and c["locked_at"].startswith(c["date"][:8])
    import archetype_engine as ae
    assert set(p) == ae.CARD_ALLOWED_KEYS
    _assert_no_forbidden(p)

    again = client.post("/card", json={}, headers=h).json()
    assert again["card_id"] == c["card_id"]                                        # 하루 1장

    cid = c["card_id"]
    r = client.patch(f"/card/{cid}", json={"hide_numbers": True, "comment": "오늘도 해냈다"}, headers=h).json()
    assert r["payload"]["metrics"] == [] and r["payload"]["rarity_pct"] is None
    assert r["payload"]["comment"] == "오늘도 해냈다"
    assert client.patch(f"/card/{cid}", json={"comment": "x" * 21}, headers=h).status_code == 422
    assert client.patch(f"/card/{cid}", json={"theme_id": "neon"}, headers=h).status_code == 422
    assert client.patch(f"/card/{cid}", json={"stickers": [{"type": "emoji", "x": 0, "y": 0}]},
                        headers=h).status_code == 422
    ok = client.patch(f"/card/{cid}", json={"stickers": [{"type": "star", "x": 0.2, "y": 0.3}],
                                            "theme_id": "forest"}, headers=h).json()
    assert ok["payload"]["theme_id"] == "forest" and len(ok["payload"]["stickers"]) == 1

    assert client.get("/card/list", headers=h).json()["cards"][0]["card_id"] == cid

    # 잠금: locked_at 을 과거로 강제
    import metrics_repo as mr
    mr._exec(f"UPDATE share_card SET locked_at = {mr._p()} WHERE card_id = {mr._p()}", ("2000-01-01T00:00:00", cid))
    assert client.patch(f"/card/{cid}", json={"theme_id": "coral"}, headers=h).status_code == 409
    assert client.get(f"/card/{cid}", headers=h).json()["locked"] is True


def test_card_isolation_between_accounts(client):
    h1 = _login(client, identity="u1")
    client.put("/metrics/today", json={"water_cups": 6}, headers=h1)
    cid = client.post("/card", json={}, headers=h1).json()["card_id"]
    h2 = _login(client, identity="u2")
    assert client.get(f"/card/{cid}", headers=h2).status_code == 404
    assert client.get("/archetype/day", headers=h2).status_code == 404
