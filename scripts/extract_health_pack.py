"""extract_health_pack.py — 코드 상수(routine_engine·coaching_engine)를 팩 1호로 추출.

정본: docs/plan/28-routine-pack-platform.md Phase 0.

팩 플랫폼 도입 **전** 코드에서 한 번 실행해 routines/packs/health_12w/v1.json 을 만든다.
이후 커리큘럼 정본은 팩 파일이고, 이 스크립트는 추출 경위를 남기는 기록이다
(도입 후 엔진이 팩을 읽으므로 다시 돌리면 같은 파일이 나와야 한다 — 왕복 검증).

    python scripts/extract_health_pack.py            # 파일과 비교만
    python scripts/extract_health_pack.py --write    # 파일 생성
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "routines" / "packs" / "health_12w" / "v1.json"

# 보조 행동(KB) 출처 라벨 → 팩 source key
_KB_SOURCE_KEYS = {
    "식약처 나트륨 저감": "mfds_sodium",
    "보건소 영양관리": "phc_nutrition",
    "WHO 신체활동 지침": "who_pa",
    "국민체육진흥 일반지침": "kspo",
    "질병청 건강생활": "kdca_life",
    "보건소 건강생활": "phc_life",
    "보건소 금연사업": "phc_smoke",
    "보건소 절주사업": "phc_drink",
}

# web/js/onboard.js TRACK_META 의 이름·설명(이모지는 아이콘 키로 대체) + routine_engine._TARGET
_TRACK_META = {
    "diet": {"name": "식이 기록", "icon": "bowl", "desc": "식사 시각·짠맛 습관을 하루 30초로 남겨요"},
    "exercise": {"name": "활동 기록", "icon": "run", "desc": "오늘 몸을 움직였는지 1탭으로 남겨요"},
    "habit": {"name": "생활 리듬", "icon": "moon", "desc": "취침 시각과 컨디션을 하루 30초로 남겨요"},
}

# 27 §1-4 T3 단계 설명
_PHASE_META = {
    "정착기": ("settle", "30초짜리 기록 하나를 매일 같은 자리에 붙여요"),
    "확장기": ("expand", "내 기준선을 읽고, 무너지는 상황을 찾아요"),
    "내재화기": ("internalize", "못 한 날에서 돌아오는 방법을 만들어요"),
    "전환기": ("transition", "3개월치 기록을 진료·검진으로 가져가요"),
}

# coaching_engine._select_keys 의 분기를 누적 규칙으로 옮긴 것(골든 테스트가 동등성 보증)
_SUPPORT_RULES = {
    "diet": {
        "rules": [
            {"when": {"eatout": ["거의 매일", "주 2~3회"]}, "add": ["soup_half", "ramen_weekly", "processed_down"]},
            {"when": {"salty": ["강함", "보통"]}, "add": ["sauce_dip", "taste_light", "water_more"]},
            {"add": ["veggie_add"]},
        ],
        "default": ["soup_half", "veggie_add"],
    },
    "exercise": {
        "rules": [
            {"when": {"now": ["거의 안 함"]}, "add": ["walk_more", "stairs", "move_break"]},
            {"unless": {"now": ["거의 안 함"]}, "add": ["walk_3x", "stretch", "walk_more"]},
            {"add": ["stretch"]},
        ],
        "default": ["walk_more", "stairs"],
    },
    "habit": {
        "rules": [
            {"when": {"focus": ["수면", None]}, "add": ["sleep_fix", "screen_off", "caffeine"]},
            {"when": {"focus": ["스트레스"]}, "add": ["breathe", "rest"]},
            {"when": {"focus": ["금연·절주"]}, "add": ["smoke_help", "drink_down"]},
            {"add": ["breathe"]},
        ],
        "default": ["sleep_fix", "breathe"],
    },
}


def build() -> dict:
    import coaching_engine as ce
    import routine_engine as eng

    cite_key = {label: key for key, label in eng._CITE.items()}
    sources = [{"key": k, "label": v} for k, v in eng._CITE.items()]
    for label, key in _KB_SOURCE_KEYS.items():
        sources.append({"key": key, "label": label})

    tracks = [{"id": t, **_TRACK_META[t], "target_noun": eng._TARGET[t],
               "recommend_when": sorted(f for f, tr in eng.FOCUS_TRACK.items() if tr == t)}
              for t in eng.TRACKS]

    phases = [{"id": _PHASE_META[name][0], "name": name, "from": lo, "to": hi,
               "desc": _PHASE_META[name][1]} for name, lo, hi in eng.PHASES]

    weeks = []
    for m in eng.WEEKS:
        w = m["w"]
        actions = {}
        for t in eng.TRACKS:
            a = eng.ROUTINE_ACTIONS[(w, t)]
            actions[t] = {"id": a["id"], "text": a["text"], "cite": cite_key[a["cite"]],
                          "minutes": a["minutes"],
                          "input": {"kind": a["input"]["kind"], "options": list(a["input"]["options"])}}
        weeks.append({"w": w, "theme": m["theme"], "goal_days": m["goal_days"],
                      "support_cap": m["support"], "mission": m["mission"], "unlock": m["unlock"],
                      "actions": actions, "ask_chips": list(eng.ASK_CHIPS[w])})

    intake = {t: [{"id": q["id"], "q": q["q"],
                   "options": [{"label": o, "value": o} for o in q["options"]]}
                  for q in ce.INTAKE_QUESTIONS[t]] for t in eng.TRACKS}

    pool = {t: [{"key": x["key"], "text": x["text"], "cite": _KB_SOURCE_KEYS[x["cite"]],
                 "tags": [x["tag"]]} for x in ce.KB[t]] for t in eng.TRACKS}

    return {
        "schema_version": 1,
        "id": "health_12w",
        "version": eng.CURRICULUM_VERSION,
        "name": "건강 기록 12주",
        "tagline": "하루 30초 기록으로 내 패턴 찾기",
        "domain": "health",
        "safety_profile": "medical",
        "weeks_total": eng.WEEKS_TOTAL,
        "phases": phases,
        "tracks": tracks,
        "intake": intake,
        "weeks": weeks,
        "support_pool": pool,
        "support_rules": _SUPPORT_RULES,
        "support_pool_cap": {"default": 4, "경고": 2},
        "banners": {t: dict(v) for t, v in eng._BANNER.items()},
        "transition": {"advance": 0.7, "simplify": 0.4},
        "sources": sources,
    }


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    data = build()
    import routine_packs as rp
    rp.Pack.model_validate(data)                      # 구조 무결성 먼저
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(dump(data), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        same = OUT.exists() and json.loads(OUT.read_text(encoding="utf-8")) == data
        print("MATCH" if same else "DIFF")
        sys.exit(0 if same else 1)
