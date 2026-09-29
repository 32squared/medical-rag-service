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


# ══════════════════════════ 팩별 자동 검사(FR-T3) ══════════════════════════
def _all_pack_keys():
    return sorted(rp.load_all())


@pytest.mark.parametrize("key", _all_pack_keys(), ids=lambda k: f"{k[0]}-v{k[1]}")
def test_every_pack_passes_lint(key):
    p = rp.load_all()[key]
    errs = rp.lint_errors(p)
    assert not errs, "\n".join(f"{e['path']} {e['rule']} {e['msg']}" for e in errs)


@pytest.mark.parametrize("key", _all_pack_keys(), ids=lambda k: f"{k[0]}-v{k[1]}")
def test_every_pack_engine_smoke(key):
    """전 주차 × 트랙 × 밴드에서 엔진이 예외 없이 유효한 값을 낸다."""
    import routine_engine as eng
    p = rp.load_all()[key]
    for w in range(0, p.weeks_total + 2):
        for t in p.track_ids + ["zzz"]:
            for b in (None, "안정", "주의", "경고"):
                a = eng.today_action(w, t, p, b)
                assert a["id"] and a["text"] and a["cite"]
                assert 0 <= eng.band_cap(b, w, p) <= 2
                items = eng.plan_items(t, {}, b, p)
                assert isinstance(eng.support_items(items, w, b, p), list)
        assert eng.phase_of(w, p) and eng.goal_days(w, p) >= 1
    assert len(eng.week_preview(None, p)) == p.weeks_total
    if p.safety_profile in ("medical", "physical"):
        assert all(eng.band_cap("경고", w, p) == 0 for w in range(1, p.weeks_total + 1))


def test_scaffold_is_valid_but_fails_lint(tmp_path):
    import pack_new
    pk = rp.Pack.model_validate(pack_new.scaffold("demo_26w", 26, ["a1", "b2"], "physical", "sport", "데모"))
    assert pk.weeks_total == 26 and [(x.from_, x.to) for x in pk.phases][-1][1] == 26
    rules = {i["rule"] for i in rp.lint_errors(pk)}
    assert "L0" in rules                                  # TODO 가 남아 있으면 배포 불가
    for n in (4, 5, 12, 26, 52):                          # 단계 분할이 어떤 기간에서도 유효
        rp.Pack.model_validate(pack_new.scaffold("demo_x", n, ["a1"], "neutral", "custom", "x"))


def test_lint_catches_content_rules():
    d = _health_raw()
    d["id"] = "lint_demo"
    d["weeks"][0]["actions"]["diet"]["text"] = "또 못 하셨네요, 오늘은 꼭 하세요"
    d["weeks"][1]["ask_chips"] = ["하나"]
    d["weeks"][2]["actions"]["diet"]["input"] = {"kind": "choice", "options": list("가나다라마바")}
    d["weeks"][0]["support_cap"] = 1
    d["tracks"][0]["icon"] = "🥗"
    d["banners"]["habit"].pop("주의")
    d["sources"][0]["label"] = "개인 블로그"
    rules = {i["rule"] for i in rp.lint_errors(rp.Pack.model_validate(d))}
    assert {"L5", "L11", "L7", "L8", "L10", "L9", "L6"} <= rules


def test_schema_file_up_to_date():
    import pack_lint
    assert pack_lint.SCHEMA_FILE.read_text(encoding="utf-8") == pack_lint.schema_text(), \
        "python scripts/pack_lint.py --schema 로 갱신"


def test_lint_icons_exist_in_frontend():
    js = (ROOT / "web" / "js" / "archetypes.js").read_text(encoding="utf-8")
    body = js[js.index("export const ICON"):]
    missing = [k for k in rp.ICONS if f"\n  {k}:" not in body and f"\n  {k}(" not in body]
    assert not missing, f"archetypes.js ICON 에 없음: {missing}"


def test_frontend_has_no_fixed_week_literals():
    """주차 수는 팩에서 온다(28 FR-F2, §10 리스크 3)."""
    hits = [f"{f.name}:{i}" for f in (ROOT / "web" / "js").glob("*.js")
            for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1) if "12주" in ln]
    assert not hits, hits
