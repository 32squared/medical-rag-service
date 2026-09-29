"""test_routine_packs.py — 루틴 팩 플랫폼(로더·무결성·골든 무회귀).

정본: docs/plan/28-routine-pack-platform.md.
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import routine_packs as rp  # noqa: E402

GOLDEN = ROOT / "tests" / "golden" / "health_12w.json"


def _health_raw():
    return json.loads((rp.PACKS_DIR / "health_12w" / "v1.json").read_text(encoding="utf-8"))


# ══════════════════════════ 레지스트리 ══════════════════════════
def test_registry_loads_default_pack():
    rp.reload()
    p = rp.get()
    assert p.id == rp.DEFAULT_PACK_ID and p.version == 1
    assert p.weeks_total == 12 and p.track_ids == ["diet", "exercise", "habit"]
    assert [(x.from_, x.to) for x in p.phases] == [(1, 2), (3, 6), (7, 10), (11, 12)]


def test_get_falls_back_to_default_and_latest():
    assert rp.get("no_such_pack").id == rp.DEFAULT_PACK_ID
    assert rp.get(rp.DEFAULT_PACK_ID, 999).version == rp.latest_version(rp.DEFAULT_PACK_ID)
    assert rp.get(rp.DEFAULT_PACK_ID, "x").id == rp.DEFAULT_PACK_ID


def test_catalog_lists_default_first():
    cat = rp.catalog()
    assert cat[0].id == rp.DEFAULT_PACK_ID
    assert len({p.id for p in cat}) == len(cat)


# ══════════════════════════ 구조 무결성(L1·L2) ══════════════════════════
def _broken(mutate):
    d = _health_raw()
    mutate(d)
    with pytest.raises(ValueError):
        rp.Pack.model_validate(d)


def test_integrity_week_count():
    _broken(lambda d: d["weeks"].pop())


def test_integrity_phase_gap():
    def m(d):
        d["phases"][1]["from"] = 4
    _broken(m)


def test_integrity_unknown_cite():
    def m(d):
        d["weeks"][0]["actions"]["diet"]["cite"] = "nowhere"
    _broken(m)


def test_integrity_actions_cover_tracks():
    def m(d):
        del d["weeks"][3]["actions"]["habit"]
    _broken(m)


def test_integrity_support_rule_refs():
    def m(d):
        d["support_rules"]["diet"]["rules"][0]["add"].append("ghost")
    _broken(m)


def test_integrity_choice_needs_options():
    def m(d):
        d["weeks"][2]["actions"]["diet"]["input"]["options"] = ["하나"]
    _broken(m)


def test_integrity_unknown_field_rejected():
    _broken(lambda d: d.update({"surprise": 1}))


def test_file_name_must_match_id_and_version(tmp_path):
    d = _health_raw()
    bad = tmp_path / "health_12w" / "v2.json"
    bad.parent.mkdir()
    bad.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        rp.load_file(bad)


def test_load_all_reports_every_bad_pack(tmp_path):
    for pid in ("health_12w", "broken_a"):
        d = _health_raw()
        d["id"] = pid
        if pid == "broken_a":
            d["weeks_total"] = 13
        f = tmp_path / "packs" / pid / "v1.json"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RuntimeError, match="broken_a"):
        rp.load_all(tmp_path / "packs")


# ══════════════════════════ 골든 무회귀 ══════════════════════════
def test_golden_health_12w_unchanged():
    """플랫폼 도입 전 코드로 만든 스냅샷과 현재 출력이 같아야 한다(FR-S3)."""
    import routine_golden
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = json.loads(routine_golden.dump(routine_golden.build()))
    for block in sorted(expected):
        assert actual.get(block) == expected[block], f"golden block differs: {block}"
    assert set(actual) == set(expected)
