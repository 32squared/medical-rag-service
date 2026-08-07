"""bff/routine_routes.py — 12주 루틴 프로그램 BFF 라우트.

정본: docs/plan/25-routine-transition-spec.md §F(API 계약).

설계:
  - **홈 1콜**(`GET /routine/today`) — 프론트가 여러 엔드포인트를 병렬 호출하면
    refresh 회전 경합으로 확정적 로그아웃이 발생한다(스펙 C2/H-7). 구조적 방어.
  - 파생값(주차·스트릭·실천율·전환)은 전부 서버에서 결정적으로 계산한다.
  - 날짜는 서버가 KST 로 확정한다(클라이언트 시각은 참고값).
  - 개인화는 동의원장 기준. 안전(응급/경고) 신호는 동의와 무관하게 항상 계산해 내린다.

의료법: 진단·처방 없음. 밴드는 '구간 안내'. 커리큘럼은 결정적 템플릿 + WC-C 백스톱.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel

import routine_engine as eng
import routine_repo as repo


# ── 요청 모델 ─────────────────────────────────────────────────────
class StartReq(BaseModel):
    track: str = "diet"
    intake: Optional[Dict] = None
    focus: Optional[str] = None
    notify_hhmm: Optional[str] = None
    mode: str = "new"                 # new | change_track | restart
    force: bool = False


class CheckinReq(BaseModel):
    program_id: Optional[str] = None
    action_id: str
    slot: str = "main"                # main | support
    status: str = "done"              # done | skip | na | undone
    value: Optional[str] = None
    barrier: Optional[str] = None
    occurred_date: Optional[str] = None
    client_ts: Optional[str] = None
    idempotency_key: Optional[str] = None


class ActionAddReq(BaseModel):
    item_key: str
    source: str = "chat"


class ReplanReq(BaseModel):
    program_id: Optional[str] = None
    mode: str = "simplify"            # simplify | advance | pause | resume
    until: Optional[str] = None


class ReportReadReq(BaseModel):
    week: int


class NotifyReq(BaseModel):
    hhmm: str
    channel: str = "inapp"


_VALID_STATUS = ("done", "skip", "na", "undone")


def _safe(fn, default=None):
    """조회 실패가 화면 전체를 깨지 않게 — 루틴은 매일 쓰는 화면이다."""
    try:
        return fn()
    except Exception:
        return default


def register(app, deps: Dict) -> None:
    """라우트 등록. deps: get_subject / persona / persona_band / consent 헬퍼."""
    get_subject = deps["get_subject"]
    persona_of = deps["persona_of"]          # (subject_id) -> persona dict | None
    band_of = deps["band_of"]                # (persona) -> '안정'|'주의'|'경고'|None
    consent_ok = deps["consent_ok"]          # (subject_id) -> (granted:set, personalize:bool)

    # ── 공통 계산 ────────────────────────────────────────────────
    def _ctx(sid: str):
        persona = _safe(lambda: persona_of(sid))
        band = _safe(lambda: band_of(persona)) if persona else None
        granted, personalize = _safe(lambda: consent_ok(sid), (set(), False))
        return persona, band, granted, personalize

    def _require_personal(granted) -> None:
        if "personal_info" not in (granted or set()):
            raise HTTPException(status_code=403, detail="personal_info_consent_required")

    def _emergency(band: Optional[str]) -> Optional[Dict]:
        if band == "응급":
            return {"kind": "emergency", "text": "지금 119·응급실로 바로 연락하세요",
                    "referral": "emergency", "dismissible": False}
        return None

    def _stats(sid: str, program: Optional[Dict]) -> Dict:
        import coaching_gamification as g
        dates = _safe(lambda: repo.done_dates(sid), []) or []
        streak = repo.streak_from(dates)
        best = repo.best_streak(dates)
        done = len(dates)
        adh = _safe(lambda: repo.program_adherence(program), 0) if program else 0
        pts = _safe(lambda: g.points(done, streak), done * 10) or 0
        return {
            "streak": streak, "best_streak": best, "done": done, "adherence": adh,
            "points": pts, "level": _safe(lambda: g.level(pts), 1) or 1,
            "badges": _safe(lambda: g.badges(best), []) or [],
            "days_since_last": _safe(lambda: repo.days_since_last_checkin(sid), 0) or 0,
            "total_done_days": done,
        }

    def _pace_adherence(program: Optional[Dict], wk: int, done_days: int, goal: int) -> int:
        """**경과일 기준** 실천율. 주차 목표(예: 7일 중 3일) 대비로 계산하면 1일차에
        33%가 되어 첫 체크인부터 'simplify'(요즘 바쁘셨죠?)가 뜬다 — 전략문서가 성패
        요인으로 지목한 '첫 성공 경험'을 정면으로 해친다. 지금까지 지날 수 있었던
        일수만 분모로 삼는다."""
        if not program:
            return 0
        elapsed = repo.day_no(program) - (max(1, wk) - 1) * 7
        elapsed = max(1, min(7, elapsed))
        expected = max(1, min(int(goal or 1), elapsed))
        return min(100, round(max(0, int(done_days or 0)) / expected * 100))

    def _coach(stats: Dict) -> Optional[Dict]:
        import coaching_adaptive as ad
        return _safe(lambda: ad.coach(int(stats.get("adherence") or 0),
                                      int(stats.get("streak") or 0),
                                      int(stats.get("days_since_last") or 0)))

    def _support_pool(program: Optional[Dict]) -> List[Dict]:
        """보조 항목 풀 — coaching_plan.items_json(생성 시 저장) 재사용."""
        if not program or not program.get("plan_id"):
            return []

        def _load():
            import json
            import rag_db
            plan = rag_db.get_latest_coaching_plan(program.get("subject_id") or "")
            if not plan:
                return []
            return json.loads(plan.get("items_json") or "[]") or []
        return _safe(_load, []) or []

    def _today_payload(sid: str) -> Dict:
        persona, band, granted, personalize = _ctx(sid)
        _require_personal(granted)
        today = repo.today_kst()
        emg = _emergency(band)
        program = _safe(lambda: repo.get_active_program(sid))

        base = {"server_date": today, "band": band, "safety": emg,
                "personalization": bool(personalize),
                "notify": _safe(lambda: repo.get_notify(sid), {"hhmm": None, "channel": "inapp"})}

        if emg:                       # 응급은 루틴 전면 중단(스펙 F-2)
            base.update({"state": "S9_PAUSED_SAFETY", "program": None, "today": None,
                         "support": [], "weeks": [], "week_days": [], "days": [],
                         "stats": None, "coach": None, "banner": None, "ask_chips": [],
                         "report_due": None, "evidence": None})
            return base

        if not program:               # 프로그램 없음 — 미리보기 행동만
            prev = eng.today_action(1, "diet")
            base.update({
                "state": "S2_DIAGNOSED" if band else "S1_NEW", "program": None,
                "today": {**prev, "status": "preview"}, "support": [], "weeks": [],
                "week_days": [], "days": [], "stats": None, "coach": None,
                "banner": eng.banner_for("diet", band), "ask_chips": [],
                "report_due": None,
                "evidence": ({"label": f"{band} 구간", "tone": "personal"} if band else None),
                "preview_weeks": eng.week_preview(band),
            })
            return base

        # ── 활성 프로그램 ──
        wk = repo.current_week(program, today)
        track = eng.normalize_track(program.get("track"))
        meta = eng.week_meta(wk)
        goal = int(meta["goal_days"])
        action = eng.today_action(wk, track)
        cap = eng.band_cap(band or program.get("band_at_start"), wk)

        ck = _safe(lambda: repo.get_checkin(program["program_id"], today, action["id"]))
        st_today = (ck or {}).get("status") or "pending"

        stats = _stats(sid, program)
        wstat = _safe(lambda: repo.week_stats(program, wk, goal),
                      {"done_days": 0, "goal_days": goal, "eff_goal": goal,
                       "na_days": 0, "adherence": 0})
        support = eng.support_items(_support_pool(program), wk, band or program.get("band_at_start"))
        sup_out = []
        for s in support:
            sck = _safe(lambda k=s.get("key"): repo.get_checkin(program["program_id"], today, k or ""))
            sup_out.append({**s, "status": (sck or {}).get("status") or "pending"})

        # 완주 판정
        dno = repo.day_no(program, today)
        state = "S4_ACTIVE"
        if program.get("status") == "paused":
            state = "S8_PAUSED"
        elif int(stats.get("days_since_last") or 0) >= 8:
            state = "S7_DORMANT"
        elif dno > 84:
            state = "S11_COMPLETED"

        unread = _safe(lambda: repo.unread_report_week(program["program_id"], wk))

        base.update({
            "state": state,
            "program": {
                "program_id": program.get("program_id"), "track": track,
                "focus": program.get("focus"), "anchor": program.get("anchor"),
                "started_on": program.get("started_on"), "week_no": wk, "day_no": dno,
                "weeks_total": 12, "phase": eng.phase_of(wk), "theme": meta["theme"],
                "mission": meta["mission"], "goal_days": goal, "item_cap": cap,
                "mode": program.get("mode") or "daily", "status": program.get("status") or "active",
            },
            "today": {**action, "status": st_today,
                      "value": (ck or {}).get("value")},
            "support": sup_out,
            "week": {"w": wk, "done_days": wstat["done_days"], "goal_days": wstat["goal_days"],
                     "adherence": wstat["adherence"], "na_days": wstat["na_days"]},
            "weeks": _safe(lambda: repo.build_week_state(program, wk), []) or [],
            "week_days": _safe(lambda: repo.week_days(program, wk), []) or [],
            "days": _safe(lambda: repo.heat_days(program), []) or [],
            "stats": stats,
            # 아직 한 번도 기록이 없으면 코치는 '반응'할 실적이 없다. 이때 adherence 0 으로
            # 재참여 문구("요즘 바쁘셨죠?")를 내보내면 시작도 안 한 사용자를 나무라는 꼴이 된다.
            "coach": ({"action": "start", "no_blame": True,
                       "message": "오늘 딱 한 가지만 남기면 시작이에요."}
                      if int(stats.get("done") or 0) == 0
                      else _coach({**stats, "adherence": _pace_adherence(
                          program, wk, wstat["done_days"], wstat["eff_goal"])})),
            "banner": eng.banner_for(track, band or program.get("band_at_start")),
            "ask_chips": eng.ask_chips(wk),
            "report_due": ({"week": unread, "unread": True} if unread else None),
            "evidence": ({"label": f"{band} 구간 기준", "tone": "personal"} if band and personalize else None),
        })
        _safe(lambda: repo.update_program(program["program_id"], last_seen_on=today))
        return base

    # ── 라우트 ───────────────────────────────────────────────────
    @app.get("/routine/today")
    def routine_today(sub: dict = Depends(get_subject)):
        return _today_payload(sub["subject_id"])

    @app.post("/routine/start")
    def routine_start(req: StartReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        persona, band, granted, _ = _ctx(sid)
        _require_personal(granted)

        track = eng.normalize_track(req.track)
        if req.track and req.track not in eng.TRACKS:
            raise HTTPException(status_code=400, detail="unknown_track")

        existing = _safe(lambda: repo.get_active_program(sid))
        if existing and req.mode == "new":
            raise HTTPException(status_code=409, detail="program_exists")
        if existing and req.mode in ("change_track", "restart"):
            _safe(lambda: repo.archive_all(sid))

        prog = eng.generate_program(track, req.intake or {}, band=band,
                                    focus=req.focus, anchor=None)

        plan_id = None                      # 보조 항목 풀은 기존 coaching_plan 에 저장(재사용)
        def _save_plan():
            import rag_db
            sess = rag_db.create_coaching_session(
                conversation_id=sid, mode="routine:" + track, track=track, band_at_start=band)
            return rag_db.save_coaching_plan(
                session_id=sess, track=track, items=prog["plan_items"], target_period="12주",
                band=band, safety_banner=prog.get("banner"),
                compliance_action=prog.get("compliance_action", "pass"), conversation_id=sid)
        plan_id = _safe(_save_plan)

        pid = repo.create_program(
            subject_id=sid, track=track, plan_id=plan_id, focus=req.focus,
            intake=req.intake or {}, band=band, item_cap=prog["item_cap"],
            curriculum_version=eng.CURRICULUM_VERSION)
        if not pid:
            raise HTTPException(status_code=500, detail="program_save_error")

        if req.notify_hhmm:
            _safe(lambda: repo.set_notify(sid, req.notify_hhmm))
        _safe(lambda: __import__("analytics_events").emit("routine_started", track=track))

        return {"program_id": pid, "plan_id": plan_id, "track": track,
                "started_on": repo.today_kst(), "week_no": 1,
                "item_cap": prog["item_cap"], "banner": prog.get("banner"),
                "preview": {"weeks": prog["weeks"]}, "today": prog["today"]}

    @app.post("/routine/checkin")
    def routine_checkin(req: CheckinReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        persona, band, granted, _ = _ctx(sid)
        _require_personal(granted)

        if req.status not in _VALID_STATUS:
            raise HTTPException(status_code=400, detail="invalid_status")
        if _emergency(band):
            return {"ok": True, "accepted": False, "reason": "emergency_block",
                    "message": "지금은 119·응급실 안내를 먼저 확인해주세요."}

        program = _safe(lambda: repo.get_active_program(sid))
        if not program or program.get("status") not in ("active", "paused"):
            return {"ok": True, "accepted": False, "reason": "program_inactive",
                    "message": "진행 중인 루틴이 없어요. 새로 시작해볼까요?"}

        today = repo.today_kst()
        occurred = (req.occurred_date or today)[:10]
        gap = repo.days_between(occurred, today)     # today - occurred
        if gap < 0:
            return {"ok": True, "accepted": False, "reason": "future_date",
                    "message": "아직 오지 않은 날짜예요."}
        if gap > 2:
            return {"ok": True, "accepted": False, "reason": "too_old",
                    "message": "이틀 이상 지난 기록은 남길 수 없어요. 오늘 날짜로 기록할까요?"}
        applied = occurred

        wk = repo.week_of(program.get("started_on") or today, applied,
                          int(program.get("paused_days") or 0))
        res = repo.upsert_checkin(
            program_id=program["program_id"], subject_id=sid, action_date=applied,
            week_no=wk, slot=(req.slot if req.slot in ("main", "support") else "main"),
            item_key=req.action_id, status=req.status, value=req.value,
            barrier=req.barrier, idempotency_key=req.idempotency_key, client_ts=req.client_ts)
        if not res:
            raise HTTPException(status_code=500, detail="checkin_error")

        goal = eng.goal_days(wk)
        wstat = _safe(lambda: repo.week_stats(program, wk, goal),
                      {"done_days": 0, "goal_days": goal, "eff_goal": goal, "adherence": 0})
        stats = _stats(sid, program)
        _safe(lambda: __import__("analytics_events").emit(
            "routine_checkin", checkin_done=(req.status == "done")))

        return {"ok": True, "accepted": True, "applied_date": applied,
                "duplicate": bool(res.get("duplicate")),
                "stats": stats, "badges_new": [],
                "week": {"w": wk, "done_days": wstat["done_days"], "goal_days": wstat["goal_days"]},
                "coach": _coach({**stats, "adherence": _pace_adherence(
                    program, wk, wstat["done_days"], wstat.get("eff_goal") or goal)}),
                "ask_chips": eng.ask_chips(wk)}

    @app.post("/routine/action/add")
    def routine_action_add(req: ActionAddReq, sub: dict = Depends(get_subject)):
        """상담 → 루틴(①→④). 정착기(1~2주)에는 서버가 거부한다(스펙 B-1)."""
        sid = sub["subject_id"]
        persona, band, granted, _ = _ctx(sid)
        _require_personal(granted)
        program = _safe(lambda: repo.get_active_program(sid))
        if not program:
            raise HTTPException(status_code=409, detail="no_program")
        wk = repo.current_week(program)
        if wk <= 2:
            raise HTTPException(status_code=409, detail="activation_lock")
        cap = eng.band_cap(band or program.get("band_at_start"), wk)
        if cap <= 0:
            raise HTTPException(status_code=409, detail="cap_reached")
        pool = _support_pool(program)
        if not any((x or {}).get("key") == req.item_key for x in pool):
            raise HTTPException(status_code=400, detail="unknown_item")
        return {"ok": True, "added_to": "today",
                "support": eng.support_items(pool, wk, band or program.get("band_at_start"))}

    @app.post("/routine/replan")
    def routine_replan(req: ReplanReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        persona, band, granted, _ = _ctx(sid)
        _require_personal(granted)
        program = _safe(lambda: repo.get_active_program(sid))
        if not program:
            raise HTTPException(status_code=409, detail="no_program")
        pid = program["program_id"]
        wk = repo.current_week(program)
        mode = req.mode

        if mode == "advance" and band == "경고":
            raise HTTPException(status_code=409, detail="advance_blocked_band")

        if mode == "simplify":
            repo.update_program(pid, item_cap=0, adherence_state="simplified")
            msg = "요즘 바쁘셨죠? 부담을 줄여 더 쉬운 목표로 다시 잡아드릴게요."
        elif mode == "advance":
            repo.update_program(pid, item_cap=eng.band_cap(band, wk), adherence_state="progressed")
            msg = "좋아요. 이번 주는 하나만 더 얹어볼게요."
        elif mode == "pause":
            repo.update_program(pid, status="paused", paused_until=req.until)
            msg = "잠시 쉬어가요. 돌아오시면 진도는 그대로 이어집니다."
        elif mode == "resume":
            extra = repo.days_between(program.get("paused_until") or repo.today_kst(),
                                      repo.today_kst())
            repo.update_program(pid, status="active", paused_until=None,
                                paused_days=int(program.get("paused_days") or 0) + max(0, extra))
            msg = "다시 시작해요. 오늘 딱 한 가지만."
        else:
            raise HTTPException(status_code=400, detail="unknown_mode")

        after = _safe(lambda: repo.get_active_program(sid)) or program
        return {"ok": True, "item_cap": int(after.get("item_cap") or 0),
                "adherence_state": after.get("adherence_state"),
                "current_week": repo.current_week(after), "message": msg}

    @app.get("/routine/week-report")
    def routine_week_report(week: Optional[int] = Query(None),
                            sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        persona, band, granted, _ = _ctx(sid)
        _require_personal(granted)
        program = _safe(lambda: repo.get_active_program(sid))
        if not program:
            raise HTTPException(status_code=409, detail="no_program")
        cur = repo.current_week(program)
        wk = int(week) if week else (_safe(lambda: repo.unread_report_week(program["program_id"], cur))
                                     or max(1, cur - 1))
        wk = eng.clamp_week(wk)
        goal = eng.goal_days(wk)
        st = _safe(lambda: repo.week_stats(program, wk, goal),
                   {"done_days": 0, "goal_days": goal, "eff_goal": goal, "na_days": 0,
                    "adherence": 0})
        trans = eng.transition(st["done_days"], st["eff_goal"], band)
        _safe(lambda: repo.save_report(
            program_id=program["program_id"], week_no=wk, done_days=st["done_days"],
            goal_days=st["goal_days"], adherence=st["adherence"],
            streak_end=repo.streak_from(repo.done_dates(sid)), na_days=st["na_days"],
            transition=trans))

        bars = []
        for w in range(1, min(cur, 12) + 1):
            s = _safe(lambda w=w: repo.week_stats(program, w, eng.goal_days(w)),
                      {"done_days": 0, "eff_goal": 1})
            bars.append({"w": w, "ratio": round(min(1.0, s["done_days"] / max(1, s["eff_goal"])), 2)})

        prev = _safe(lambda: repo.week_stats(program, wk - 1, eng.goal_days(wk - 1))) if wk > 1 else None
        delta = None
        if prev:
            diff = st["done_days"] - prev["done_days"]
            delta = ("지난주보다 " + (f"{diff}일 더" if diff > 0 else f"{abs(diff)}일 적게")) if diff else "지난주와 같아요"

        nxt = eng.week_meta(min(12, wk + 1))
        return {
            "week_no": wk, "theme": eng.week_meta(wk)["theme"],
            "done_days": st["done_days"], "goal_days": st["goal_days"],
            "na_days": st["na_days"], "adherence": st["adherence"],
            "streak_end": repo.streak_from(repo.done_dates(sid)),
            "days": _safe(lambda: repo.week_days(program, wk), []) or [],
            "weekly_bars": bars, "delta": delta,
            "trend_label": "안정유지" if st["adherence"] >= 70 else "불안정반복",
            "next": {"week_no": min(12, wk + 1), "theme": nxt["theme"],
                     "mission": nxt["mission"], "transition": trans,
                     "item_cap": eng.band_cap(band, min(12, wk + 1))},
            "questions": eng.ask_chips(wk),
            "banner": eng.banner_for(program.get("track") or "diet", band),
        }

    @app.post("/routine/report/read")
    def routine_report_read(req: ReportReadReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        program = _safe(lambda: repo.get_active_program(sid))
        if program:
            _safe(lambda: repo.mark_report_read(program["program_id"], eng.clamp_week(req.week)))
            _safe(lambda: __import__("analytics_events").emit("routine_report_read"))
        return {"ok": True}

    @app.put("/routine/notify")
    def routine_notify(req: NotifyReq, sub: dict = Depends(get_subject)):
        hh = (req.hhmm or "").strip()
        try:
            h = int(hh.split(":")[0])
        except Exception:
            raise HTTPException(status_code=422, detail="notify_time_not_allowed")
        if not (8 <= h <= 20):                # 21:00~07:59 금지(스펙 F-5)
            raise HTTPException(status_code=422, detail="notify_time_not_allowed")
        ok = repo.set_notify(sub["subject_id"], hh, req.channel or "inapp")
        if not ok:
            raise HTTPException(status_code=500, detail="notify_save_error")
        return {"ok": True, "hhmm": hh, "channel": req.channel or "inapp"}

    @app.get("/diagnosis")
    def diagnosis(sub: dict = Depends(get_subject)):
        """상태 진단(③) — 페르소나 PHR 기반. 수치는 '구간 안내'이며 진단이 아니다."""
        sid = sub["subject_id"]
        persona, band, granted, personalize = _ctx(sid)
        _require_personal(granted)
        notice = "구간 안내이며 진단이 아닙니다. 판정과 해석은 의료기관에서 받으세요."
        emg = _emergency(band)

        if not personalize or not persona:
            return {"band": None, "items": [], "missing": [], "personalization": False,
                    "recommended": {"track": "diet", "focus": None, "evidence_phrase": None},
                    "practice_profile": [], "safety": emg, "notice": notice}

        items: List[Dict] = []
        try:
            import vital_rules as vr
            vitals = (persona or {}).get("vitals") or []
            if vitals:
                for f in (vr.run(vitals[-1], locale=persona.get("locale", "KR"),
                                 population=persona.get("population", "adult"),
                                 context=persona.get("context", "clinic")) or []):
                    if f.get("sentence"):
                        continue
                    items.append({"key": f.get("signal_key"), "label": f.get("display") or f.get("signal_key"),
                                  "state": f.get("label_user")})
        except Exception:
            items = []

        track = "diet"
        focus = None
        for it in items:
            if it.get("state") in ("주의", "경고"):
                k = (it.get("key") or "")
                if "pressure" in k or "bp" in k:
                    track, focus = "diet", "bp"
                elif "spo2" in k or "temperature" in k or "heart" in k:
                    track, focus = "habit", "sleep_stress"
                elif "bmi" in k:
                    track, focus = "exercise", "weight_activity"
                break

        practice = []
        prog = _safe(lambda: repo.get_active_program(sid))
        if prog:
            dates = _safe(lambda: repo.done_dates(sid), []) or []
            if dates:
                practice = [{"label": "루틴 실천", "days": len(dates),
                             "weeks": repo.current_week(prog)}]

        return {"band": band, "items": items, "missing": [],
                "personalization": True,
                "recommended": {"track": track, "focus": focus,
                                "evidence_phrase": (f"{band} 구간 기준" if band else None)},
                "practice_profile": practice, "safety": emg, "notice": notice}
