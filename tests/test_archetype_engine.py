"""test_archetype_engine.py — 오늘의 나 재미 레이어 순수 계산.

정본: docs/design/todays-me-mockups/02-dev-requirements.md §5, 01-cross-review.md C1~C6.
검증 축: 완료 조합→아키타입 7+0 / 깨어남≠완료 / E01 자정 유예 / 취침 귀속 / 환산·하이라이트 /
        희귀도 하한 / 웰니스 타입 동점 규칙 / 카드 화이트리스트 fail-closed / 무비난(미완료 미노출).
"""
from datetime import datetime, timezone, timedelta

import pytest

import archetype_engine as ae

KST = timezone(timedelta(hours=9))


def _m(**kw):
    base = {"water_cups": 0, "steps": None, "steps_source": "none", "steps_confirmed": 0,
            "mind_seconds": 0, "mind_sessions": 0}
    base.update(kw)
    return base


# ── 아키타입 조합 ─────────────────────────────────────────────
@pytest.mark.parametrize("tracks,aid", [
    ((), None), (("diet",), "hydration_king"), (("exercise",), "step_wizard"), (("habit",), "mindful_warrior"),
    (("diet", "exercise"), "sunny_runner"), (("exercise", "habit"), "night_owl_reformed"),
    (("diet", "habit"), "zen_barista"), (("diet", "exercise", "habit"), "balance_monk"),
    (("habit", "diet"), "zen_barista"),                # 순서 무관
    (("diet", "zzz"), "hydration_king"),               # 미지 트랙 무시
])
def test_archetype_combo(tracks, aid):
    assert ae.archetype_for(tracks) == aid


def test_seven_archetypes_have_full_dictionary():
    assert len(ae.ARCHETYPES) == 7
    for k, v in ae.ARCHETYPES.items():
        info = ae.archetype_info(k)
        assert info["name_en"] and info["name_ko"] and info["lore"] and info["bg"].startswith("#")
        assert set(info["elements"]) <= {"water", "bolt", "moon"}
    assert ae.archetype_info("nope") is None


# ── 완료 판정과 깨어남 ────────────────────────────────────────
def test_completion_uses_goals_only():
    assert ae.completed_tracks(_m(water_cups=6)) == ["diet"]
    assert ae.completed_tracks(_m(water_cups=5)) == []
    assert ae.completed_tracks(_m(steps=6000)) == ["exercise"]
    assert ae.completed_tracks(_m(steps=100, steps_confirmed=1)) == ["exercise"]   # 수동 확정
    assert ae.completed_tracks(_m(mind_sessions=1)) == ["habit"]
    assert ae.completed_tracks(_m(water_cups=6, steps=6400, mind_sessions=1)) == ["diet", "exercise", "habit"]


def test_awake_is_not_complete():
    st = ae.track_state(_m(water_cups=1, steps=1000, mind_seconds=5))
    assert st["water"]["awake"] and not st["water"]["complete"]
    assert st["steps"]["awake"] and not st["steps"]["complete"]
    assert st["mind"]["awake"] and not st["mind"]["complete"]
    st0 = ae.track_state(None)
    assert not any(t["awake"] for t in st0.values())


def test_goals_read_from_single_constant(monkeypatch):
    monkeypatch.setitem(ae.GOALS, "water_cups", 3)
    assert ae.completed_tracks(_m(water_cups=3)) == ["diet"]


# ── 시간 규칙 ────────────────────────────────────────────────
def test_e01_grace_ten_minutes():
    server = datetime(2026, 9, 3, 0, 3, tzinfo=KST)
    assert ae.applied_date("2026-09-02T23:55:00+09:00", server) == "2026-09-02"     # 유예 적용
    assert ae.applied_date("2026-09-02T23:49:59+09:00", server) == "2026-09-03"     # 23:50 전 → 서버 날짜
    server_late = datetime(2026, 9, 3, 0, 11, tzinfo=KST)
    assert ae.applied_date("2026-09-02T23:58:00+09:00", server_late) == "2026-09-03"  # 00:10 지남
    assert ae.applied_date(None, server) == "2026-09-03"
    assert ae.applied_date("garbage", server) == "2026-09-03"


def test_bedtime_before_five_belongs_to_previous_night():
    assert ae.bedtime_metric_date("2026-09-03T01:20:00+09:00") == "2026-09-02"
    assert ae.bedtime_metric_date("2026-09-02T23:10:00+09:00") == "2026-09-02"
    assert ae.bedtime_metric_date("2026-09-03T05:00:00+09:00") == "2026-09-03"
    assert ae.bedtime_metric_date("x") is None


def test_card_lock_is_next_day_0010():
    assert ae.card_lock_at("2026-09-02").startswith("2026-09-03T00:10")


def test_steps_stale_after_30_minutes():
    now = datetime(2026, 9, 3, 12, 0, tzinfo=KST)
    assert ae.steps_stale("2026-09-03T11:29:00+09:00", now) is True
    assert ae.steps_stale("2026-09-03T11:31:00+09:00", now) is False
    assert ae.steps_stale(None, now) is True


# ── 환산·행·태그·하이라이트 ──────────────────────────────────
def test_conversion_zero_renders_nothing():
    assert ae.conversion_text("water_cups", 6) == "= 작은 화분 3개"
    assert ae.conversion_text("water_cups", 1) is None
    assert ae.conversion_text("steps", 6400) == "= 한강 다리 2개"
    assert ae.conversion_text("mindful_min", 7) == "= 노래 2곡"
    assert ae.conversion_text("mindful_min", 100) == "= 노래 8곡"     # 상한
    assert ae.conversion_text("bogus", 5) is None


def test_metrics_rows_skip_zero_and_unmeasured():
    rows = ae.metrics_rows(_m(water_cups=6, steps=None, mind_seconds=420))
    kinds = [r["kind"] for r in rows]
    assert kinds == ["water_cups", "mindful_min"]           # 걸음 미측정 → 행 없음
    assert rows[1]["value"] == 7 and rows[1]["conversion_text"] == "= 노래 2곡"
    assert ae.metrics_rows(None) == []


def test_why_tags_only_completed_tracks():
    m = _m(water_cups=6, steps=6400, mind_seconds=420, mind_sessions=1)
    assert ae.why_tags(m, ["diet", "exercise", "habit"]) == ["물 6컵", "6,400걸음", "마음챙김 7분"]
    assert ae.why_tags(m, ["habit"]) == ["마음챙김 7분"]
    assert ae.why_tags(m, []) == []


def test_highlight_self_record_no_ties():
    hist = [_m(water_cups=5), _m(water_cups=4)]
    assert ae.highlight(_m(water_cups=6), hist)["type"] == "water"
    assert ae.highlight(_m(water_cups=5), hist)["type"] != "water"        # 동률 제외
    assert ae.highlight(_m(water_cups=6, steps=6000, mind_sessions=1), [])["type"] == "f1"
    assert ae.highlight(_m(water_cups=1), [], week_record_days=4)["text"] == "이번 주 4일째 기록한 날"
    assert ae.highlight(None, [])["type"] == "f3"


def test_no_blame_vocabulary_in_outputs():
    banned = ("실패", "결석", "미달", "놓친", "남음", "부족")
    texts = [ae.conversion_text("water_cups", 2), ae.highlight(None, [])["text"], ae.rarity_text(0)]
    for t in ae.why_tags(_m(water_cups=6), ["diet"]):
        texts.append(t)
    for a in ae.ARCHETYPES.values():
        texts.append(a["lore"])
    for t in texts:
        assert t is None or not any(b in t for b in banned), t


# ── 희귀도 ──────────────────────────────────────────────────
def test_rarity_sample_floor_100():
    assert ae.rarity_pct(12, 99) is None
    assert ae.rarity_pct(12, 100) == 12
    assert ae.rarity_text(None) is None
    assert ae.rarity_text(0) == "이번 달 이 캐릭터 만난 사람 1% 미만"
    assert ae.rarity_text(12) == "이번 달 이 캐릭터 만난 사람 12%"
    assert len(ae.rarity_text(12)) <= 20


# ── 웰니스 타입 ─────────────────────────────────────────────
def test_wellness_type_majority_and_q4_tiebreak():
    assert ae.assign_wellness_type([0, 0, 0, 0]) == "miracle_morning_dreamer"
    assert ae.assign_wellness_type([0, 4, 0, 4]) == "baby_godsaeng"          # 동점 → Q4
    assert ae.assign_wellness_type([1, 1, 2, 4]) == "micro_wellness_sloth"    # 다수결
    assert ae.assign_wellness_type([0, 1, 2, 3]) == "ritual_fairy"            # 4자 동점 → Q4
    assert ae.assign_wellness_type([0, 1, 2]) is None
    assert ae.assign_wellness_type([9, 0, 0, 0]) is None
    assert len(ae.WELLNESS_TYPES) == 5 and len(ae.WELLNESS_QUIZ) == 4
    for q in ae.WELLNESS_QUIZ:
        assert len(q["options"]) == 5 and all(len(o) <= 12 for o in q["options"])
    assert ae.wellness_type_info("baby_godsaeng")["label"] == "갓생 신생아 타입"


# ── 공유 카드 화이트리스트 ──────────────────────────────────
def _card(**kw):
    args = dict(metric_date="2026-09-02", m=_m(water_cups=6, steps=6400, mind_seconds=420, mind_sessions=1),
                archetype_id="balance_monk", rarity=12, theme_id="coral", stickers=[], comment=None,
                hide_numbers=False, wellness_type_id="baby_godsaeng", band="안정")
    args.update(kw)
    return ae.build_card_payload(**args)


def test_card_payload_whitelist_and_gate():
    p = _card()
    assert set(p) == ae.CARD_ALLOWED_KEYS
    assert p["archetype_en"] == "Balance Monk" and p["wellness_type_label"] == "갓생 신생아 타입"
    assert [r["kind"] for r in p["metrics"]] == ["water_cups", "steps", "mindful_min"]
    assert _card(band="경고") is None and _card(band="응급") is None
    assert _card(archetype_id=None) is None
    h = _card(hide_numbers=True)
    assert h["metrics"] == [] and h["rarity_pct"] is None
    assert _card(theme_id="neon")["theme_id"] == "coral"


def test_card_payload_rejects_unknown_or_forbidden_keys():
    p = _card()
    with pytest.raises(ValueError):
        ae.assert_card_payload({**p, "systolic_bp": 130})
    with pytest.raises(ValueError):
        ae.assert_card_payload({**p, "metrics": [{}] * 4})
    with pytest.raises(ValueError):
        ae.assert_card_payload({**p, "comment": "x" * 21})


def test_sticker_validation():
    ok = [{"type": "star", "x": 0.1, "y": 0.2}] * 3
    assert ae.validate_stickers(ok) is None
    assert ae.validate_stickers(ok + [{"type": "star", "x": 0, "y": 0}]) == "sticker_limit"   # 종류별 3 초과
    assert ae.validate_stickers([{"type": "emoji", "x": 0, "y": 0}]) == "sticker_type"
    assert ae.validate_stickers([{"type": "moon", "x": 1.2, "y": 0}]) == "sticker_position"
    assert ae.validate_stickers([{"type": "drop", "x": 0, "y": 0}] * 7) == "sticker_limit"
