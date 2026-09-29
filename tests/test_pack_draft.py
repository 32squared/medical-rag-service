"""test_pack_draft.py — LLM 초안 도구(28 D8). 가짜 LLM 으로 조립·수리·안전 경계를 고정한다."""
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pack_draft as pd  # noqa: E402
import routine_packs as rp  # noqa: E402

BRIEF = {
    "id": "run_demo_8w", "name": "달리기 입문 8주", "domain": "sport", "safety_profile": "physical",
    "weeks": 8, "audience": "운동 습관이 없는 직장인", "goal": "주 3회 가볍게 달리기",
    "tracks": [{"id": "outdoor", "name": "밖에서 달리기", "icon": "run"},
               {"id": "indoor", "name": "집에서 준비", "icon": "home"}],
    "sources": [{"key": "kspo", "label": "국민체육진흥공단 국민체력100", "url": "https://nfa.kspo.or.kr"},
                {"key": "who", "label": "WHO 신체활동 지침", "url": None}],
}
SKELETON = {
    "tagline": "하루 한 번, 천천히 달리는 습관",
    "tracks": {"outdoor": {"desc": "동네를 천천히 달리고 느낌을 남겨요", "target_noun": "달리기"},
               "indoor": {"desc": "집에서 준비운동과 걷기로 이어가요", "target_noun": "준비"}},
    "phases": {p: {"desc": "짧게 시작해요"} for p in ("settle", "build", "use", "keep")},
    "intake": {t: [{"id": "level", "q": "요즘 운동은 어떤가요?", "why": "시작 강도를 맞춰요",
                    "options": [{"label": "거의 안 해요", "value": "none"}, {"label": "가끔 걸어요", "value": "walk"}]},
                   {"id": "anchor", "q": "언제 할까요?", "why": "그때 알려드려요",
                    "options": [{"label": "아침", "value": "morning"}, {"label": "저녁", "value": "evening"}]}]
               for t in ("outdoor", "indoor")},
    "support_pool": {t: [{"key": "warmup", "text": "시작 전 5분 걷기", "cite": "kspo"},
                         {"key": "water", "text": "마치고 물 한 컵", "cite": "who"}] for t in ("outdoor", "indoor")},
    "support_rules": {t: {"rules": [{"when": {"level": ["none"]}, "add": ["warmup", "ghost"]}],
                          "default": ["water"]} for t in ("outdoor", "indoor")},
    "banners": {t: {"주의": "측정값이 주의 구간이에요. 천천히, 불편한 날은 쉬어 가요.",
                    "경고": "측정값이 경고 구간이에요. 달리기 전에 의료진과 먼저 상담해 주세요."}
                for t in ("outdoor", "indoor")},
}


def _week(w, text=None, cite="kspo"):
    a = {"slug": f"run{w}", "text": text or f"{w}주차 천천히 달리고 느낌 탭", "cite": cite, "minutes": 15,
         "input": ({"kind": "tap", "options": []} if w in (1, 5, 8)      # 첫 주·다시 잇기·확정
                   else {"kind": "choice", "options": ["가뿐", "보통", "힘듦"]})}
    wa = {"slug": "warn", "text": "달리기는 쉬고 몸 상태만 탭", "cite": "kspo", "minutes": 1,
          "input": {"kind": "tap", "options": []}}
    return {"w": w, "theme": f"{w}주 천천히", "mission": "7일 중 3일, 정한 때에 달리기", "goal_days": 5,
            "actions": {"outdoor": a, "indoor": dict(a, slug=f"home{w}", text=f"{w}주차 집에서 준비운동 후 탭")},
            "warning_actions": {"outdoor": wa, "indoor": wa},
            "ask_chips": ["얼마나 천천히 달리나요?", "숨이 차면 어떻게 하나요?", "신발은 뭘 신나요?"]}


class FakeLLM:
    """REQUEST 마커로 요청 종류를 구분. bad={주차: (text, cite)} 는 첫 작성에만 끼운다."""

    def __init__(self, bad=None):
        self.bad = dict(bad or {})
        self.calls = []

    def __call__(self, system, user):
        self.calls.append(user)
        if "REQUEST: skeleton" in user:
            return "```json\n" + json.dumps(SKELETON, ensure_ascii=False) + "\n```"
        wks = json.loads(re.search(r"REQUEST_WEEKS: (\[[^\]]*\])", user).group(1))
        out = []
        for w in wks:
            if w in self.bad and "고칠 점" not in user:
                text, cite = self.bad[w]
                out.append(_week(w, text, cite))
            else:
                out.append(_week(w))
        return json.dumps({"weeks": out}, ensure_ascii=False)


def test_draft_builds_valid_pack_without_repairs():
    llm = FakeLLM()
    res = pd.draft(BRIEF, llm, log=lambda *_: None)
    pk = rp.Pack.model_validate(res["pack"])
    assert res["errors"] == [] and res["rounds"] == 0
    assert rp.lint_errors(pk) == []
    assert pk.weeks_total == 8 and pk.weeks[0].goal_days == 3            # 1주차 목표는 3 이하로 자름
    assert all(w.support_cap == 0 for w in pk.weeks if w.w <= pk.phases[0].to)   # 구조는 스캐폴드가 결정
    assert pk.support_rules["outdoor"].rules[0].add == ["warmup"]        # 없는 key 는 결정적으로 버림
    assert len(llm.calls) == 1 + 2                                        # skeleton + 8주를 6주씩


def test_repair_rewrites_only_offending_week():
    llm = FakeLLM(bad={2: ("또 못 하셨네요, 오늘은 꼭 달리세요", "kspo")})
    res = pd.draft(BRIEF, llm, log=lambda *_: None)
    assert res["errors"] == [] and res["rounds"] == 1
    repair = [c for c in llm.calls if "고칠 점" in c]
    assert len(repair) == 1 and "REQUEST_WEEKS: [2]" in repair[0] and "L5" in repair[0]
    assert "또 못" not in json.dumps(res["pack"], ensure_ascii=False)


def test_invented_source_is_sent_back_not_kept():
    llm = FakeLLM(bad={5: ("5주차 천천히 달리고 느낌 탭", "blog_xyz")})
    res = pd.draft(BRIEF, llm, log=lambda *_: None)
    assert res["errors"] == []
    assert any("blog_xyz" in c and "REQUEST_WEEKS: [5]" in c for c in llm.calls)
    cites = {a["cite"] for w in res["pack"]["weeks"] for a in w["actions"].values()}
    assert cites <= {"kspo", "who"}


def test_unrepaired_problems_are_reported():
    class Stubborn(FakeLLM):                      # 3주차는 몇 번을 다시 써도 금칙어
        def __call__(self, system, user):
            out = super().__call__(system, user)
            if "REQUEST_WEEKS" not in user:
                return out
            d = json.loads(out)
            d["weeks"] = [_week(3, "게으름은 금물, 오늘은 꼭 달리기") if w["w"] == 3 else w for w in d["weeks"]]
            return json.dumps(d, ensure_ascii=False)
    res = pd.draft(BRIEF, Stubborn(), rounds=2, log=lambda *_: None)
    assert res["rounds"] == 2
    assert res["errors"] and all("weeks[3]" in e for e in res["errors"])


def test_medical_brief_rejects_non_whitelisted_source():
    b = dict(BRIEF, id="med_demo", safety_profile="medical",
             sources=[{"key": "blog", "label": "개인 블로그", "url": None}])
    with pytest.raises(pd.BriefError):
        pd.load_brief(b)
    with pytest.raises(pd.BriefError):
        pd.load_brief(dict(BRIEF, tracks=[{"id": "outdoor", "name": "x", "icon": "🏃"}]))


def test_write_goes_to_drafts_not_registry(tmp_path):
    res = pd.draft(BRIEF, FakeLLM(), log=lambda *_: None)
    f = pd.write_draft(res, BRIEF, tmp_path)
    assert f == tmp_path / "run_demo_8w" / "v1.json" and (f.parent / "review.md").exists()
    assert "사람이 꼭 볼 것" in (f.parent / "review.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        pd.write_draft(res, BRIEF, rp.PACKS_DIR)
    assert "run_demo_8w" not in rp.pack_ids()


def test_quality_checks_send_back_backward_chips_and_banners():
    class Sloppy(FakeLLM):
        def __call__(self, system, user):
            out = pd._json_from(super().__call__(system, user))
            if "고칠 점" in user:
                return json.dumps(out, ensure_ascii=False)
            if "REQUEST: skeleton" in user:
                out["banners"]["outdoor"]["경고"] = "심장질환이나 임신 중이면 상담하세요"
            else:
                for w in out["weeks"]:
                    if w["w"] == 4:
                        w["ask_chips"][0] = "오늘 느낌은 어땠나요?"
            return json.dumps(out, ensure_ascii=False)
    llm = Sloppy()
    res = pd.draft(BRIEF, llm, log=lambda *_: None)
    assert res["errors"] == [] and res["rounds"] == 1
    fixes = [c for c in llm.calls if "고칠 점" in c]
    assert any("REQUEST: skeleton" in c and "측정값이 경고 구간" in c for c in fixes)
    assert any("REQUEST_WEEKS: [4]" in c and "어땠나요" in c for c in fixes)
