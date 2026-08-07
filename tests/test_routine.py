"""test_routine.py — 12주 루틴 프로그램(엔진·영속·BFF 라우트).

정본: docs/plan/25-routine-transition-spec.md.
검증 축: 커리큘럼 완전성 / 의료법 컴플라 / 밴드 캡 / 멱등 체크인 / 날짜 규칙 /
        파생 계산(주차·스트릭·실천율) / 첫 성공 경험 톤 / 계정 격리.
"""
import pathlib
import sqlite3

import pytest

import routine_engine as eng

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ══════════════════════════════ 엔진(순수) ══════════════════════════════
def test_curriculum_complete_and_compliant():
    """12주 × 3트랙 전량 존재 + 출처 필수 + WC-C 컴플라 통과."""
    for w in range(1, 13):
        for t in eng.TRACKS:
            a = eng.today_action(w, t)
            assert a["id"] and a["text"] and a["cite"], (w, t)
            assert eng.compliance_check([a["text"]])["ok"], (w, t, a["text"])
    assert len(eng.WEEKS) == 12
    assert [m["goal_days"] for m in eng.WEEKS] == [3, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 4]


def test_phases_2_4_4_2():
    assert eng.phase_of(1) == eng.phase_of(2) == "정착기"
    assert eng.phase_of(3) == eng.phase_of(6) == "확장기"
    assert eng.phase_of(7) == eng.phase_of(10) == "내재화기"
    assert eng.phase_of(11) == eng.phase_of(12) == "전환기"


def test_band_cap_warning_always_zero():
    """경고 밴드는 12주 내내 보조 항목 0 — 안전 캡(스펙 B-4)."""
    for w in range(1, 13):
        assert eng.band_cap("경고", w) == 0
    assert eng.band_cap("안정", 1) == 0        # 정착기는 밴드 무관 0
    assert eng.band_cap("안정", 7) == 2
    assert eng.band_cap("주의", 7) == 1        # 주의는 최대 1


def test_transition_thresholds():
    assert eng.transition(4, 5) == "advance"          # 80% ≥ 70
    assert eng.transition(2, 5) == "hold"             # 40% 구간
    assert eng.transition(1, 5) == "simplify"         # < 40%
    assert eng.transition(5, 5, "경고") == "hold"      # 경고는 advance 금지


def test_engine_never_raises_on_bad_input():
    for bad in (None, 0, 99, -3, "x", 1.5):
        assert 1 <= eng.clamp_week(bad) <= 12
        assert eng.phase_of(bad)
        assert eng.goal_days(bad) > 0
        assert eng.today_action(bad, "zzz")["id"]
    assert eng.support_items(None, 5, "안정") == []
    assert eng.support_items([], 5, "안정") == []


def test_support_items_respects_cap():
    pool = [{"key": f"k{i}", "text": f"t{i}", "cite": "c"} for i in range(5)]
    assert eng.support_items(pool, 1, "안정") == []        # 정착기 0
    assert len(eng.support_items(pool, 5, "안정")) == 1
    assert len(eng.support_items(pool, 7, "안정")) == 2
    assert eng.support_items(pool, 7, "경고") == []


def test_generate_program_shape():
    p = eng.generate_program("diet", {"eatout": "주 2~3회"}, band="경고")
    assert p["item_cap"] == 0 and len(p["weeks"]) == 12
    assert p["today"]["id"] and p["banner"]
    assert p["compliance_action"] in ("pass", "band_capped")


# ══════════════════════════════ 영속 ══════════════════════════════
@pytest.fixture
def repo(tmp_path, monkeypatch):
    db = str(tmp_path / "routine.db")
    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import dbcommon
    monkeypatch.setattr(dbcommon, "DB_PATH", db)
    monkeypatch.setattr(dbcommon, "_use_postgres", False)
    import routine_repo as rr
    monkeypatch.setattr(rr, "_SCHEMA_ENSURED", False)
    rr.ensure_schema()
    return rr


def test_checkin_is_idempotent(repo):
    pid = repo.create_program(subject_id="s1", track="diet", started_on="2026-08-01")
    for _ in range(3):
        repo.upsert_checkin(program_id=pid, subject_id="s1", action_date="2026-08-01",
                            week_no=1, slot="main", item_key="w1:log_meal_time", status="done")
    assert len(repo.list_checkins(pid)) == 1          # UNIQUE 로 중복 구조적 차단
    assert repo.done_dates("s1") == ["2026-08-01"]


def test_undo_updates_same_row(repo):
    pid = repo.create_program(subject_id="s1", track="diet", started_on="2026-08-01")
    repo.upsert_checkin(program_id=pid, subject_id="s1", action_date="2026-08-01", week_no=1,
                        slot="main", item_key="a", status="done")
    r = repo.upsert_checkin(program_id=pid, subject_id="s1", action_date="2026-08-01", week_no=1,
                            slot="main", item_key="a", status="undone")
    assert r["undo_count"] == 1 and len(repo.list_checkins(pid)) == 1
    assert repo.done_dates("s1") == []                # undone 은 done 집합에서 빠진다


def test_streak_and_week_stats(repo):
    pid = repo.create_program(subject_id="s1", track="diet", started_on="2026-08-01")
    prog = repo.get_active_program("s1")
    for d, st in [("2026-08-01", "done"), ("2026-08-02", "done"), ("2026-08-03", "done"),
                  ("2026-08-04", "na"), ("2026-08-05", "skip")]:
        repo.upsert_checkin(program_id=pid, subject_id="s1", action_date=d, week_no=1,
                            slot="main", item_key="w1:log_meal_time", status=st)
    s = repo.week_stats(prog, 1, eng.goal_days(1))
    assert s["done_days"] == 3
    assert s["goal_days"] == 3 and s["eff_goal"] == 2   # 표시 목표 불변 / na 는 분모만 차감
    assert s["adherence"] == 100
    assert repo.streak_from(repo.done_dates("s1"), "2026-08-03") == 3
    assert repo.best_streak(repo.done_dates("s1")) == 3


def test_week_of_and_pause(repo):
    assert repo.week_of("2026-08-01", "2026-08-07") == 1
    assert repo.week_of("2026-08-01", "2026-08-08") == 2
    assert repo.week_of("2026-08-01", "2026-08-15", paused_days=7) == 2   # 일시정지분 제외


def test_program_isolation_between_accounts(repo):
    repo.create_program(subject_id="a", track="diet", started_on="2026-08-01")
    assert repo.get_active_program("a") is not None
    assert repo.get_active_program("b") is None


# ══════════════════════════════ BFF 라우트 ══════════════════════════════
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
    monkeypatch.setattr(consent_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(account_db, "_SCHEMA_ENSURED", False)
    monkeypatch.setattr(rag_db, "_COACHING_SCHEMA_ENSURED", False)
    monkeypatch.setattr(routine_repo, "_SCHEMA_ENSURED", False)
    from fastapi.testclient import TestClient
    from bff.app import create_app
    return TestClient(create_app())


def _login(c, identity="routine-user", persona="hypertension_senior"):
    tx = c.post("/auth/pass/start", json={}).json()["tx_id"]
    tok = c.post("/auth/pass/callback",
                 json={"tx_id": tx, "mock_identity": identity}).json()
    h = {"Authorization": "Bearer " + tok["access_token"]}
    c.post("/consent", json={"item_key": "personal_info", "action": "grant"}, headers=h)
    if persona:
        c.post("/persona/select", json={"persona_id": persona}, headers=h)
    return h


def test_today_without_program_previews(client):
    h = _login(client)
    d = client.get("/routine/today", headers=h).json()
    assert d["program"] is None and d["today"]["status"] == "preview"
    assert d["stats"] is None and d["weeks"] == []


def test_start_then_today_and_duplicate_blocked(client):
    h = _login(client)
    s = client.post("/routine/start", json={"track": "diet", "intake": {"eatout": "주 2~3회"}},
                    headers=h)
    assert s.status_code == 200 and len(s.json()["preview"]["weeks"]) == 12
    assert client.post("/routine/start", json={"track": "diet"},
                       headers=h).status_code == 409           # program_exists

    d = client.get("/routine/today", headers=h).json()
    assert d["state"] == "S4_ACTIVE"
    assert d["program"]["week_no"] == 1 and d["program"]["phase"] == "정착기"
    assert d["program"]["item_cap"] == 0                        # 경고 밴드
    assert len(d["weeks"]) == 12 and len(d["week_days"]) == 7
    assert d["banner"] and "진료" in d["banner"]                 # 경고 → 진료 우선 배너


def test_checkin_flow_and_date_rules(client):
    h = _login(client)
    client.post("/routine/start", json={"track": "diet"}, headers=h)
    t = client.get("/routine/today", headers=h).json()
    aid = t["today"]["id"]

    r = client.post("/routine/checkin",
                    json={"action_id": aid, "status": "done", "value": "18~20시"},
                    headers=h).json()
    assert r["accepted"] and r["stats"]["streak"] == 1
    assert r["coach"]["action"] != "simplify"                   # 첫 성공 경험 톤

    dup = client.post("/routine/checkin", json={"action_id": aid, "status": "done"},
                      headers=h).json()
    assert dup["duplicate"] and dup["stats"]["streak"] == 1      # 스트릭 부풀지 않음

    old = client.post("/routine/checkin",
                      json={"action_id": aid, "status": "done", "occurred_date": "2020-01-01"},
                      headers=h).json()
    assert old["accepted"] is False and old["reason"] == "too_old"
    fut = client.post("/routine/checkin",
                      json={"action_id": aid, "status": "done", "occurred_date": "2099-01-01"},
                      headers=h).json()
    assert fut["accepted"] is False and fut["reason"] == "future_date"


def test_coach_start_message_before_first_checkin(client):
    h = _login(client, identity="tone", persona="healthy_office")
    client.post("/routine/start", json={"track": "habit"}, headers=h)
    d = client.get("/routine/today", headers=h).json()
    assert d["coach"]["action"] == "start"                       # 재참여 문구 금지
    assert d["coach"]["no_blame"] is True


def test_activation_lock_in_settling_phase(client):
    h = _login(client)
    client.post("/routine/start", json={"track": "diet"}, headers=h)
    r = client.post("/routine/action/add", json={"item_key": "soup_half"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "activation_lock"


def test_notify_time_window(client):
    h = _login(client)
    assert client.put("/routine/notify", json={"hhmm": "22:00"}, headers=h).status_code == 422
    assert client.put("/routine/notify", json={"hhmm": "07:00"}, headers=h).status_code == 422
    assert client.put("/routine/notify", json={"hhmm": "09:00"}, headers=h).status_code == 200


def test_week_report_and_read(client):
    h = _login(client)
    client.post("/routine/start", json={"track": "diet"}, headers=h)
    t = client.get("/routine/today", headers=h).json()
    client.post("/routine/checkin", json={"action_id": t["today"]["id"], "status": "done"},
                headers=h)
    wr = client.get("/routine/week-report", headers=h).json()
    assert wr["week_no"] == 1 and wr["done_days"] == 1 and wr["goal_days"] == 3
    assert wr["next"]["week_no"] == 2 and wr["questions"]
    assert client.post("/routine/report/read", json={"week": 1}, headers=h).status_code == 200


def test_diagnosis_requires_consent_but_keeps_safety(client):
    h = _login(client)
    d = client.get("/diagnosis", headers=h).json()
    assert d["band"] == "경고" and d["items"]
    assert "진단이 아닙니다" in d["notice"]                        # 의료법 고지 유지


def test_routine_requires_personal_info_consent(client):
    tx = client.post("/auth/pass/start", json={}).json()["tx_id"]
    tok = client.post("/auth/pass/callback",
                      json={"tx_id": tx, "mock_identity": "no-consent"}).json()
    h = {"Authorization": "Bearer " + tok["access_token"]}
    assert client.get("/routine/today", headers=h).status_code == 403


def test_accounts_are_isolated(client):
    a = _login(client, identity="acc-a")
    client.post("/routine/start", json={"track": "diet"}, headers=a)
    b = _login(client, identity="acc-b")
    assert client.get("/routine/today", headers=b).json()["program"] is None
