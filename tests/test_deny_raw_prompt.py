# -*- coding: utf-8 -*-
"""개인 구간 라벨 금지 항목(11 §2-B)이 raw 모드 프롬프트에서도 막히는지 고정.

배경: deny 4종(LDL·eGFR·골밀도·요단백)은 band 모드에서만 막혀 있었다(시드가 없어 구조적으로).
raw 모드는 PHR 원문을 그대로 주고 규칙 9-L1 이 "범위 안/밖을 사실로 말하라"고 해, 모델이
LDL·eGFR 도 기준 구간에 넣을 수 있었다. 예외는 규칙 '안'(L1 과 L2 사이)에 심는다 — 프롬프트
끝에 덧붙인 예외는 앞 원칙에 눌려 무력했다(PHR 활용 0/10 실측).
금지 목록은 vital_rules.PERSONAL_BAND_DENY 한 곳에서 읽는다(온톨로지 연동 시 대체 자리).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vital_rules as V  # noqa: E402
from rag_engine import _build_rag_system_prompt as B  # noqa: E402

NAMES = list(V.PERSONAL_BAND_DENY.values())


# ── 단일 원천 · band 게이트 ──────────────────────────────────

def test_single_source_has_four_items():
    assert set(V.PERSONAL_BAND_DENY) == {
        "ldl_cholesterol", "egfr", "bmd_tscore", "urine_protein_dipstick"}


def test_band_gate_denies_listed_items():
    for key in V.PERSONAL_BAND_DENY:
        r = V.lookup_band(key, 100)
        assert r["match"] == "denied" and r["label_user"] is None, key


def test_band_gate_still_bands_other_items():
    r = V.lookup_band("blood_pressure", {"systolic": 135, "diastolic": 85})
    assert r["match"] == "ok" and r["label_user"] is not None


# ── raw 모드 프롬프트 (default 스타일) ──────────────────────

def _raw():
    return B("q", [], personal_kind="raw")


def test_exclusion_sits_inside_rule9_between_L1_and_L2():
    p = _raw()
    i_l1 = p.index("· L1 기준 대비 분류")
    i_ex = p.index("· L1 적용 제외")
    i_l2 = p.index("· L2 항목별 추세")
    assert i_l1 < i_ex < i_l2
    block = p[i_ex:i_l2]
    for n in NAMES:
        assert n in block, n
    assert "기준 수치를 사용자의 값" in block      # 병치 금지
    assert "의료진이 판단합니다" in block          # 대체 문장


def test_rule2d_points_to_exclusion():
    p = _raw()
    i2 = p.index("2. [컨텍스트 외 정보 금지]")
    i3 = p.index("3. [근거 충돌 시 보수성]")
    assert "L1 적용 제외 항목은 병기·분류하지 않는다" in p[i2:i3]


def test_always_rule_points_to_exclusion():
    assert "L1 적용 제외 항목은 병기·분류 없이 값만" in _raw()


def test_no_unrendered_placeholder():
    p = _raw()
    assert "{_deny_names}" not in p and "{deny_names}" not in p


# ── persly-safe ──────────────────────────────────────────────

def test_persly_safe_has_exclusion():
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "{deny_names}" not in p
    for n in NAMES:
        assert n in p, n
    assert "범위에 넣지 않습니다" in p
    assert "기준 수치를 사용자의 값 옆에 두지 않으며" in p


# ── 과잉 억제 방지 ───────────────────────────────────────────
# 실측(dev rev 00051): persly-safe 가 '의료진이 판단합니다' 문장을 공복혈당에도 붙여
# 비 deny 수치의 L1(허용·유용)이 6건 → 0건으로 사라졌다. 예외는 네 항목에만 걸려야 한다.

def test_default_exclusion_scoped_to_four_items():
    p = _raw()
    block = p[p.index("· L1 적용 제외"):p.index("· L2 항목별 추세")]
    assert "네 항목에만 적용" in block
    assert "공복혈당" in block and "L1대로 분류" in block


def test_persly_safe_exclusion_scoped_to_four_items():
    p = B("q", [], personal_kind="raw", style="persly-safe")
    assert "예외는 다음 네 항목뿐" in p
    assert "이 문장은 네 항목에만 쓰고 다른 수치에는 쓰지 않습니다" in p
    assert "범위 밖이면 범위 밖이라고 말합니다" in p      # 비 deny 수치의 L1 을 적극 지시
