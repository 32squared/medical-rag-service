"""test_routine_packs_runtime.py — 비건강 팩의 엔진·컴플라·저장소·라우트 동작.

정본: docs/plan/28-routine-pack-platform.md §3·§5-1.
"""
import json

import pytest

import routine_packs as rp
from test_routine import client, _login  # noqa: F401  (픽스처 재사용)


def _health_raw():
    return json.loads((rp.PACKS_DIR / "health_12w" / "v1.json").read_text(encoding="utf-8"))


def _demo_pack(pid="demo_5w", profile="neutral", weeks=5):
    """최소 팩: 2트랙, 단계 3개. 경고 치환 행동·누적 규칙 포함."""
    def act(w, t, kind="tap", opts=()):
        return {"id": f"w{w}:{t}", "text": f"{w}주차 {t} 기록", "cite": "src",
                "minutes": 5, "input": {"kind": kind, "options": list(opts)}}
    wk = []
    for w in range(1, weeks + 1):
        wk.append({"w": w, "theme": f"{w}주 테마", "goal_days": 3 if w == 1 else 5,
                   "support_cap": 0 if w <= 2 else 2, "mission": f"{w}주 미션",
                   "actions": {"read": act(w, "read"),
                               "listen": act(w, "listen", "scale", ["술술", "보통", "더듬"])},
                   "warning_actions": ({"read": act(w, "read_safe")} if w == 3 else {}),
                   "ask_chips": ["질문 하나", "질문 둘", "질문 셋"]})
    return {
        "id": pid, "version": 1, "name": "데모 팩", "domain": "language",
        "safety_profile": profile, "weeks_total": weeks,
        "phases": [{"id": "a", "name": "정착", "from": 1, "to": 2},
                   {"id": "b", "name": "쌓기", "from": 3, "to": weeks - 1},
                   {"id": "c", "name": "유지", "from": weeks, "to": weeks}],
        "tracks": [{"id": "read", "name": "읽기"}, {"id": "listen", "name": "듣기"}],
        "intake": {"read": [{"id": "level", "q": "지금 수준은?", "options": [
            {"label": "처음이에요", "value": "zero"}, {"label": "조금 해요", "value": "some"}]}]},
        "weeks": wk,
        "support_pool": {"read": [{"key": "kana", "text": "가나 5개", "cite": "src"},
                                  {"key": "shadow", "text": "1분 섀도잉", "cite": "src"}]},
        "support_rules": {"read": {"rules": [
            {"when": {"level": ["zero", None]}, "add": ["kana"]},
            {"unless": {"level": ["zero"]}, "add": ["shadow"]}], "default": ["shadow"]}},
        "sources": [{"key": "src", "label": "공식 교재"}],
    }


@pytest.fixture
def demo_packs(tmp_path, monkeypatch):
    """기본 팩 + 데모 팩 2종(neutral 5주, physical 6주)으로 레지스트리 교체."""
    health = _health_raw()
    root = tmp_path / "packs"
    for d in (health, _demo_pack(), _demo_pack("demo_phys", "physical", 6)):
        f = root / d["id"] / "v1.json"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rp, "PACKS_DIR", root)
    rp.reload()
    yield rp
    monkeypatch.undo()
    rp.reload()


# ══════════════════════════ 엔진·컴플라·저장소 ══════════════════════════
def test_engine_on_neutral_pack(demo_packs):
    import routine_engine as eng
    p = rp.get("demo_5w")
    assert eng.clamp_week(99, p) == 5 and eng.phase_of(4, p) == "쌓기"
    assert eng.band_cap("경고", 4, p) == 2                 # neutral: 밴드 캡 없음
    assert eng.band_cap("경고", 1, p) == 0                 # 주차 support_cap 은 그대로
    assert eng.transition(5, 5, "경고", p) == "advance"   # neutral: advance 차단 없음
    assert eng.today_action(3, "read", p, "경고")["id"] == "w3:read_safe"   # 경고 치환
    assert eng.today_action(3, "read", p, "안정")["id"] == "w3:read"
    assert eng.today_action(1, "zzz", p)["id"] == "w1:read"                 # 모르는 트랙 → 첫 트랙
    assert eng.today_action(1, "read", p)["cite"] == "공식 교재"           # 출처 키 → 라벨
    assert eng.plan_keys("read", {}, None, p) == ["kana", "shadow"]        # 미응답 = when 의 null, unless 는 미해당
    assert eng.plan_keys("read", {"level": "zero"}, None, p) == ["kana"]
    assert eng.plan_keys("read", {"level": "some"}, None, p) == ["shadow"]
    assert eng.plan_keys("listen", {}, None, p) == []
    assert len(eng.week_preview(None, p)) == 5


def test_engine_on_physical_pack_keeps_band_caps(demo_packs):
    import routine_engine as eng
    p = rp.get("demo_phys")
    assert eng.band_cap("경고", 4, p) == 0 and eng.band_cap("주의", 4, p) == 1
    assert eng.transition(5, 5, "경고", p) == "hold"


def test_compliance_profiles_add_rules_only():
    import coaching_compliance as cc
    assert cc.check_plan("6개월이면 싱글 달성", None, "physical")["action"] == "blocked"
    assert cc.check_plan("N3 합격 보장", None, "neutral")["action"] == "blocked"
    assert cc.check_plan("무릎이 아프면 파스를 붙이세요", None, "physical")["action"] == "blocked"
    assert cc.check_plan("통증이 있으면 오늘은 쉬고 해당없음을 누르세요", None, "physical")["ok"]
    assert cc.check_plan("고혈압이 좋아져요", None, "neutral")["action"] == "blocked"   # 기본 규칙은 전 프로필
    assert cc.check_plan("국물은 절반만 남기기")["ok"]                                  # 기존 시그니처 호환


def test_repo_week_of_respects_weeks_total():
    import routine_repo as rr
    assert rr.week_of("2026-08-01", "2026-12-31") == 12
    assert rr.week_of("2026-08-01", "2026-12-31", weeks_total=26) == 22
    assert rr.weeks_total_of({"weeks_total": 26}) == 26 and rr.weeks_total_of({}) == 12


# ══════════════════════════ 라우트 ══════════════════════════
def test_packs_catalog_route(client, demo_packs):
    h = _login(client, identity="pk-cat", persona="hypertension_senior")   # 경고 밴드
    r = client.get("/routine/packs", headers=h).json()
    ids = [p["id"] for p in r["packs"]]
    assert ids[0] == "health_12w" and set(ids) == {"health_12w", "demo_5w", "demo_phys"}
    by = {p["id"]: p for p in r["packs"]}
    assert by["health_12w"]["recommended"] and by["health_12w"]["available"]
    assert by["demo_5w"]["available"] and by["demo_5w"]["weeks_total"] == 5
    assert by["demo_phys"]["available"] is False and by["demo_phys"]["reason"] == "clearance_required"
    q = by["demo_5w"]["tracks"][0]["intake"][0]
    assert q["options"][0] == {"label": "처음이에요", "value": "zero"}


def test_start_non_health_pack_and_today(client, demo_packs):
    import routine_repo as rr
    h = _login(client, identity="pk-start", persona="healthy_office")
    assert client.post("/routine/start", json={"pack_id": "nope"}, headers=h).status_code == 400
    assert client.post("/routine/start", json={"pack_id": "demo_5w", "track": "diet"},
                       headers=h).status_code == 400
    r = client.post("/routine/start", json={"pack_id": "demo_5w", "track": "read",
                                            "intake": {"level": "some"}}, headers=h)
    assert r.status_code == 200 and r.json()["pack_id"] == "demo_5w" and r.json()["weeks_total"] == 5
    t = client.get("/routine/today", headers=h).json()
    pid = t["program"]["program_id"]
    assert t["program"]["weeks_total"] == 5 and t["program"]["pack_id"] == "demo_5w"
    assert t["pack"]["id"] == "demo_5w"
    assert [x["name"] for x in t["pack"]["phases"]] == ["정착", "쌓기", "유지"]
    assert t["today"]["id"] == "w1:read" and len(t["weeks"]) == 5
    ck = client.post("/routine/checkin", json={"action_id": "w1:read", "status": "done"}, headers=h).json()
    assert ck["accepted"] and ck["week"]["goal_days"] == 3

    # 4주차 → 보조 행동은 팩 규칙으로 계산(level=some → shadow)
    rr.update_program(pid, started_on=rr.add_days(rr.today_kst(), -21))
    t = client.get("/routine/today", headers=h).json()
    assert t["program"]["week_no"] == 4 and [s["key"] for s in t["support"]] == ["shadow"]
    rep = client.get("/routine/week-report?week=5", headers=h).json()
    assert rep["week_no"] == 5 and rep["next"]["week_no"] == 5 and rep["weeks_total"] == 5
    # 기간을 넘기면 완주 상태 — 5주 × 7일 기준
    rr.update_program(pid, started_on=rr.add_days(rr.today_kst(), -40))
    t = client.get("/routine/today", headers=h).json()
    assert t["program"]["week_no"] == 5 and t["state"] == "S11_COMPLETED"


def test_physical_pack_blocked_in_warning_band(client, demo_packs):
    h = _login(client, identity="pk-warn", persona="hypertension_senior")
    r = client.post("/routine/start", json={"pack_id": "demo_phys", "track": "read"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "clearance_required"
    r = client.post("/routine/start", json={"pack_id": "demo_5w", "track": "read"}, headers=h)
    assert r.status_code == 200                           # neutral 은 경고 밴드에서도 시작 가능


def test_existing_program_rows_default_to_health_pack(client):
    """025 이전 행(pack 컬럼 NULL)도 건강 12주로 계산된다."""
    import routine_repo as rr
    from dbcommon import get_conn
    h = _login(client, identity="pk-legacy", persona="healthy_office")
    pid = client.post("/routine/start", json={"track": "diet"}, headers=h).json()["program_id"]
    with get_conn() as (conn, cur):
        cur.execute("UPDATE routine_program SET pack_id = NULL, pack_version = NULL "
                    "WHERE program_id = ?", (pid,))
        conn.commit()
    t = client.get("/routine/today", headers=h).json()
    assert t["program"]["pack_id"] == "health_12w" and t["program"]["weeks_total"] == 12
    assert t["pack"]["version"] == 1                     # 최신(v2)이 아니라 시작 당시 v1
    assert t["today"]["text"] == rp.get("health_12w", 1).weeks[0].actions["diet"].text
    assert rr.get_program(pid)["pack_id"] is None
