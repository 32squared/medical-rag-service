"""
마이헬스케어 P0 BFF (FastAPI) — 인증·동의검증·라우팅·RAG 프록시.

정본: docs/plan/23-p0-detailed-design.md §4. 모든 개인화/방향2 게이트는 동의원장
(consent_db)을 진실원천으로 판정 → RAG 에 헤더만 전달(원시값·진단명 미전달).
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query

import account_db
import consent_db
from app_env import is_prod

from . import pass_adapter, rag_client, tokens
from .models import (
    AccessResp,
    ChatReq,
    ChatResp,
    CoachingCheckinReq,
    CoachingPlanReq,
    ConsentReq,
    FacilitiesReq,
    MeResp,
    PassCallbackReq,
    PassStartReq,
    PassStartResp,
    PersonaReq,
    RefreshReq,
    TokenResp,
)
from .tokens import hash_token, issue_access_token, new_refresh_token, verify_access_token


def _emit_consent(action: str, item_key: str) -> None:
    try:
        import analytics_events as ae
        ae.emit("consent_granted" if action == "grant" else "consent_revoked",
                consent_item=item_key)
    except Exception:
        pass


def _today_kst() -> str:
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")


def _kst_date(iso: str) -> str:
    """UTC ISO 타임스탬프 → KST(UTC+9) 날짜(YYYY-MM-DD). checkin ts(UTC)와 오늘(KST) 정합."""
    from datetime import datetime, timezone, timedelta
    try:
        dt = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    except Exception:
        return (iso or "")[:10]


def _streak_from_dates(done_dates: set) -> int:
    """오늘부터 거꾸로 연속된 실천 일수(KST)."""
    from datetime import datetime, timedelta
    if not done_dates:
        return 0
    cur = datetime.strptime(_today_kst(), "%Y-%m-%d")
    s = 0
    while cur.strftime("%Y-%m-%d") in done_dates:
        s += 1
        cur = cur - timedelta(days=1)
    return s


# ── 페르소나(데모 합성 PHR — 개인화 체험) ─────────────────────
_PERSONAS = None


def _load_personas():
    global _PERSONAS
    if _PERSONAS is None:
        import json as _j
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_personas", "personas.json")
        try:
            with open(path, encoding="utf-8") as f:
                _PERSONAS = _j.load(f).get("personas", [])
        except Exception:
            _PERSONAS = []
    return _PERSONAS


def _persona(pid):
    return next((p for p in _load_personas() if p.get("id") == pid), None) if pid else None


def _persona_agent_input(persona):
    import json as _j
    vitals = (persona or {}).get("vitals") or []
    return {"Vital Signs": _j.dumps(vitals, ensure_ascii=False) if vitals else "",
            "Air Quality Score": (persona or {}).get("air_quality") or "",
            "PHR": (persona or {}).get("phr") or "{}"}


def _persona_band(persona):
    try:
        import vital_rules as vr
        import wellness_router as wr
        vitals = (persona or {}).get("vitals") or []
        if not vitals:
            return None
        raw = vr.run(vitals[-1], locale=persona.get("locale", "KR"),
                     population=persona.get("population", "adult"),
                     context=persona.get("context", "clinic"))
        return wr.worst_band([f.get("label_user") for f in raw])
    except Exception:
        return None


# 페르소나 태그 → 추천질문용 관심주제/기저질환(suggested_questions 테이블 키와 정합).
_TAG_TOPIC = {"혈압": "혈압", "혈압주의": "혈압", "고혈압": "혈압", "혈당": "혈당",
              "당뇨": "혈당", "당뇨병": "혈당", "콜레스테롤": "콜레스테롤", "고지혈증": "콜레스테롤",
              "체중": "체중", "비만": "체중", "수면": "수면", "운동": "운동",
              "식단": "식단", "스트레스": "스트레스"}
_TAG_COND = {"고혈압": "고혈압", "당뇨": "당뇨", "당뇨병": "당뇨", "고지혈증": "고지혈증", "비만": "비만"}


def _persona_topics_conditions(persona):
    """페르소나 tags → (관심주제, 기저질환). 기저질환은 호출 측에서 민감정보 동의 확인 후 전달."""
    topics, conds = [], []
    for t in (persona or {}).get("tags") or []:
        tp = _TAG_TOPIC.get(t)
        if tp and tp not in topics:
            topics.append(tp)
        cd = _TAG_COND.get(t)
        if cd and cd not in conds:
            conds.append(cd)
    return topics, conds


def get_subject(authorization: Optional[str] = Header(None)) -> dict:
    """Bearer access 토큰 → {subject_id, session_id}. 위조·만료·세션철회·탈퇴를 거부(401).

    방어 다중화: (1) HMAC 서명·만료 검증 (2) **반드시 live 세션 요구**(sid 없거나
    철회/만료면 거부 — null-sid 우회 차단) (3) 계정 status=active 확인(탈퇴/휴면 차단).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    payload = verify_access_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="invalid_token")
    sid = payload.get("sid")
    if not sid or account_db.get_active_session(sid) is None:   # live 세션 필수
        raise HTTPException(status_code=401, detail="session_revoked")
    acct = account_db.get_account(payload.get("sub"))
    if not acct or acct.get("status") != "active":              # 탈퇴/휴면 차단
        raise HTTPException(status_code=401, detail="account_inactive")
    return {"subject_id": payload.get("sub"), "session_id": sid}


def _validate_runtime_config() -> None:
    """프로덕션 fail-fast — 보안 필수 설정 누락/기본값이면 부팅 거부(개별 가드의 1차 방어선)."""
    if not is_prod():
        return
    problems = []
    sec = os.environ.get("BFF_TOKEN_SECRET")
    if not sec or sec == tokens._DEV_SECRET:
        problems.append("BFF_TOKEN_SECRET")
    if not os.environ.get("ACCOUNT_CI_HMAC_KEY"):
        problems.append("ACCOUNT_CI_HMAC_KEY")
    if pass_adapter.PROVIDER == "mock" and not os.environ.get("ALLOW_MOCK_AUTH"):
        problems.append("PASS_PROVIDER(real)")
    if problems:
        raise RuntimeError("BFF prod config insecure/missing: " + ", ".join(problems))


def create_app() -> FastAPI:
    _validate_runtime_config()
    app = FastAPI(title="마이헬스케어 BFF", version="0.1.0")

    # CORS — 명시 allow-list 만(와일드카드 금지). 프론트(다른 오리진) 연동용, 기본 off.
    origins = [o.strip() for o in os.environ.get("BFF_CORS_ORIGINS", "").split(",") if o.strip()]
    if origins:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_credentials=True,
            allow_methods=["*"], allow_headers=["*"],
        )

    # 프론트(web/) 같은 오리진 서빙 → CORS 불필요(BFF 가 SPA+API 동시 호스팅).
    # SPA 는 /app/, API 는 루트(/auth·/consent…). web/ 디렉토리 있을 때만 마운트.
    try:
        _web = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
        if os.path.isdir(_web):
            from fastapi.staticfiles import StaticFiles
            app.mount("/app", StaticFiles(directory=_web, html=True), name="web")
    except Exception:
        pass

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    # ── 인증 ─────────────────────────────────────────────────
    @app.post("/auth/pass/start", response_model=PassStartResp)
    def pass_start(req: PassStartReq):
        return pass_adapter.start_verification(return_url=req.return_url)

    @app.post("/auth/pass/callback", response_model=TokenResp)
    def pass_callback(req: PassCallbackReq):
        identity = pass_adapter.verify(req.tx_id, mock_identity=req.mock_identity)
        ci = (identity.get("ci") or "").strip()
        if not ci:   # 빈 CI 는 UNIQUE 충돌로 다수 사용자를 한 계정에 병합 → 거부
            raise HTTPException(status_code=400, detail="identity_missing")
        ci_hash = account_db.hash_ci(ci)
        di_hash = account_db.hash_ci(identity.get("di") or "")
        account_id = account_db.upsert_account_by_ci(ci_hash, di_hash=di_hash)
        if not account_id:
            raise HTTPException(status_code=500, detail="account_error")
        # 탈퇴 계정 재로그인 = 재가입: 계정 재활성 + 이전 동의 전부 철회(재동의 강제,
        # append-only 원장 유지). 탈퇴가 stale 동의로 개인화를 부활시키지 못하게.
        acct = account_db.get_account(account_id)
        if acct and acct.get("status") == "withdrawn":
            account_db.reactivate_account(account_id)
            for k in consent_db.granted_items(consent_db.get_records(account_id)):
                consent_db.revoke(account_id, k, source="reactivation")
        refresh = new_refresh_token()
        session_id = account_db.create_session(account_id, hash_token(refresh), device="web")
        if not session_id:
            raise HTTPException(status_code=500, detail="session_error")
        access = issue_access_token(account_id, session_id=session_id)
        return {"access_token": access, "refresh_token": refresh,
                "session_id": session_id, "subject_id": account_id}

    @app.post("/auth/refresh", response_model=AccessResp)
    def auth_refresh(req: RefreshReq):
        sess = account_db.get_active_session(req.session_id)
        if not sess or hash_token(req.refresh_token) != sess.get("refresh_hash"):
            raise HTTPException(status_code=401, detail="invalid_refresh")
        acct = account_db.get_account(sess["subject_id"])
        if not acct or acct.get("status") != "active":
            raise HTTPException(status_code=401, detail="account_inactive")
        # refresh 회전(1회용): 새 refresh 발급 + 기존 무효화 → 탈취 토큰 재사용 차단
        new_refresh = new_refresh_token()
        if not account_db.rotate_session_refresh(
                req.session_id, sess["refresh_hash"], hash_token(new_refresh)):
            raise HTTPException(status_code=401, detail="refresh_reuse")
        token = issue_access_token(sess["subject_id"], session_id=req.session_id)
        return {"access_token": token, "refresh_token": new_refresh}

    @app.post("/auth/logout")
    def auth_logout(sub: dict = Depends(get_subject)):
        if sub["session_id"]:
            account_db.revoke_session(sub["session_id"])
        return {"ok": True}

    # ── 동의 ─────────────────────────────────────────────────
    @app.get("/consent/items")
    def consent_items():
        return {"items": [
            {"item_key": k, "title": v["title"], "required": v["required"]}
            for k, v in consent_db.CONSENT_ITEMS.items()
        ]}

    @app.post("/consent")
    def post_consent(req: ConsentReq, sub: dict = Depends(get_subject)):
        if req.action not in (consent_db.GRANT, consent_db.REVOKE):
            raise HTTPException(status_code=400, detail="invalid_action")
        if req.item_key not in consent_db.CONSENT_ITEMS:
            raise HTTPException(status_code=400, detail="unknown_item")
        rid = consent_db.record_consent(
            sub["subject_id"], req.item_key, req.action,
            item_version=req.item_version, source=req.source)
        if not rid:
            raise HTTPException(status_code=500, detail="consent_write_error")
        _emit_consent(req.action, req.item_key)
        return {"ok": True}

    @app.get("/consent/history")
    def consent_history(sub: dict = Depends(get_subject),
                        item_key: Optional[str] = Query(None)):
        rows = consent_db.history(sub["subject_id"], item_key=item_key)
        return {"history": [
            {"item_key": r["item_key"], "action": r["action"],
             "source": r.get("source"), "created_at": r["created_at"]}
            for r in rows
        ]}

    # ── 계정 ─────────────────────────────────────────────────
    @app.get("/me", response_model=MeResp)
    def me(sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        acct = account_db.get_account(sid)
        records = consent_db.get_records(sid)
        granted = consent_db.granted_items(records)
        consent = [
            {"item_key": k, "title": v["title"], "required": v["required"],
             "granted": k in granted}
            for k, v in consent_db.CONSENT_ITEMS.items()
        ]
        return {"subject_id": sid, "status": (acct or {}).get("status", "unknown"),
                "consent": consent, "missing_required": consent_db.missing_required(records)}

    @app.delete("/me")
    def withdraw(sub: dict = Depends(get_subject)):
        # 이력 보존, status=withdrawn. 세션 철회 실패는 5xx 로 표면화(조용한 부분실패 방지).
        if not account_db.withdraw_account(sub["subject_id"]):
            raise HTTPException(status_code=500, detail="withdraw_incomplete")
        try:                      # 루틴 프로그램도 함께 보관 처리(스펙 E27)
            import routine_repo
            routine_repo.archive_all(sub["subject_id"])
        except Exception:
            pass
        return {"ok": True}

    # ── 의료 채팅(RAG 프록시) ────────────────────────────────
    @app.post("/chat", response_model=ChatResp)
    def chat(req: ChatReq, sub: dict = Depends(get_subject)):
        records = consent_db.get_records(sub["subject_id"])
        granted = consent_db.granted_items(records)
        if "personal_info" not in granted:
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        import account_db
        persona = _persona(account_db.get_persona(sub["subject_id"]))
        # 개인화 플래그=동의 기준(페르소나 선택 시 sensitive 자동동의). 신호는 agent_input(페르소나)로 전달.
        personalize = consent_db.personalization_allowed(records, cross_border_needed=req.cross_border)
        # 국외이전 ack 는 **원장 기준**으로만 1 — 클라이언트 flag 만으로 국외경로 신호를
        # 보내지 않음(cross_border 동의 없으면 ack=0, 원문 국외 라우팅 차단).
        cross_border_ack = bool(req.cross_border) and ("cross_border" in granted)
        rag = rag_client.chat(
            req.message, conversation_id=req.conversation_id,
            personalization=personalize, cross_border_ack=cross_border_ack,
            user_id=sub["subject_id"],
            agent_input=_persona_agent_input(persona) if persona else None)
        # 채팅 히스토리 영속(개인별, conversation_id=subject_id) — 재로그인 복원용. 실패는 무시(대화 우선).
        try:
            import rag_db
            rag_db.save_chat_message(conversation_id=sub["subject_id"], role="user", text=req.message)
            ans = (rag or {}).get("answer") or (rag or {}).get("echo") or ""
            rag_db.save_chat_message(conversation_id=sub["subject_id"], role="ai", text=ans,
                                     citations=(rag or {}).get("citations"), personalize=personalize)
        except Exception:
            pass
        # 상황 되묻기(문진) — 순수 followups.clarify. 이미 문진 답을 실은 질의면 재문진 안 함.
        clarifiers = None
        if "문진:" not in req.message:
            try:
                import followups
                clarifiers = followups.clarify(req.message)
            except Exception:
                clarifiers = None
        return {"personalization": personalize, "rag": rag, "clarifiers": clarifiers}

    @app.get("/chat/history")
    def chat_history(sub: dict = Depends(get_subject)):
        import json as _json
        import rag_db
        out = []
        for r in rag_db.get_chat_history(sub["subject_id"], limit=50):
            m = {"role": r.get("role"), "text": r.get("text")}
            if r.get("role") == "ai":
                try:
                    m["citations"] = _json.loads(r.get("citations_json") or "null") or []
                except Exception:
                    m["citations"] = []
                m["personalize"] = bool(r.get("personalize"))
            out.append(m)
        return {"messages": out}

    @app.get("/home")
    def home(sub: dict = Depends(get_subject)):
        import account_db
        sid = sub["subject_id"]
        records = consent_db.get_records(sid)
        granted = consent_db.granted_items(records)
        if "personal_info" not in granted:
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        persona = _persona(account_db.get_persona(sid))
        band = _persona_band(persona) if persona else None
        # 선제 카드(결정적·비식별) — 페르소나 밴드 신호 → 오늘 챙길 것 1개(과부하 금지).
        # coaching_missed_days 가 없으면 R4(코칭 재참여) 규칙이 영원히 죽는다(스펙 E51).
        try:
            import routine_repo as _rr
            _missed = _rr.days_since_last_checkin(sid)
        except Exception:
            _missed = 0
        sig = {"band": band, "warning_days": 3 if band in ("주의", "경고") else 0,
               "coaching_missed_days": _missed}
        cards = []
        suggested = []
        try:
            import anticipatory_engine as ae
            top = ae.should_surface(sig)
            if top:
                cards.append({"kind": top.get("kind"), "priority": top.get("priority"),
                              "text": top.get("text"), "referral": top.get("referral"),
                              "note": top.get("note")})
            suggested = list(ae.anticipated_questions(sig))
        except Exception:
            pass
        # 추천 질문 — 선제 예상질문 + 프로필(태그→주제/기저질환) 기반, 중복제거·상한.
        try:
            import suggested_questions as sq
            topics, conds = _persona_topics_conditions(persona)
            conds = conds if "sensitive_info" in granted else None   # 기저질환=민감, 동의 시에만
            for q in sq.suggest(topics, conds):
                if q not in suggested:
                    suggested.append(q)
        except Exception:
            pass
        return {"cards": cards, "suggested": suggested[:5],
                "persona": ({"name": persona.get("name"), "emoji": persona.get("emoji", ""),
                             "band": band} if persona else None),
                "personalization": consent_db.personalization_allowed(records)}

    # ── 코칭(개인별 영속 — conversation_id=subject_id 로 재로그인 복원) ──
    @app.get("/coaching/config")
    def coaching_config():
        import coaching_engine as ce
        return {"tracks": [{"key": t, "intake": ce.get_intake(t)} for t in ce.supported_tracks()]}

    @app.get("/coaching")
    def coaching_get(sub: dict = Depends(get_subject)):
        import json as _json
        import rag_db
        sid = sub["subject_id"]
        plan = rag_db.get_latest_coaching_plan(sid)
        if not plan:
            return {"plan": None, "stats": {"done": 0, "streak": 0}}
        try:
            items = _json.loads(plan.get("items_json") or "[]")
        except Exception:
            items = []
        done_all = [c for c in rag_db.get_coaching_checkins(plan["plan_id"]) if int(c.get("done") or 0)]
        done_dates = {_kst_date(c.get("ts")) for c in done_all}
        today = _today_kst()
        done_today = {c.get("item_key") for c in done_all if _kst_date(c.get("ts")) == today}
        for it in items:
            it["done_today"] = it.get("key") in done_today
        return {"plan": {"plan_id": plan["plan_id"], "track": plan.get("track"),
                         "items": items, "period": plan.get("target_period"),
                         "banner": plan.get("safety_banner")},
                "stats": {"done": len(done_all), "streak": _streak_from_dates(done_dates)}}

    @app.post("/coaching/plan")
    def coaching_plan(req: CoachingPlanReq, sub: dict = Depends(get_subject)):
        import coaching_engine as ce
        import rag_db
        import account_db
        sid = sub["subject_id"]
        band = _persona_band(_persona(account_db.get_persona(sid)))   # 페르소나 밴드 → 배너·캡
        try:
            plan = ce.generate_plan(req.track, req.intake or {}, band=band)
        except ValueError:
            raise HTTPException(status_code=400, detail="unknown_track")
        session_id = rag_db.create_coaching_session(
            conversation_id=sid, mode="wellness:" + req.track, track=req.track, band_at_start=band)
        plan_id = rag_db.save_coaching_plan(
            session_id=session_id, track=req.track, items=plan["items"],
            target_period=plan["period"], band=plan.get("band"),
            safety_banner=plan.get("banner"),
            compliance_action=plan.get("compliance_action", "pass"), conversation_id=sid)
        if not plan_id:
            raise HTTPException(status_code=500, detail="plan_save_error")
        return {"plan_id": plan_id, "track": req.track, "header": plan["header"],
                "items": plan["items"], "period": plan["period"], "banner": plan.get("banner")}

    @app.post("/coaching/checkin")
    def coaching_checkin(req: CoachingCheckinReq, sub: dict = Depends(get_subject)):
        import rag_db
        rid = rag_db.record_coaching_checkin(
            plan_id=req.plan_id, item_key=req.item_key, done=req.done,
            conversation_id=sub["subject_id"])
        if not rid:
            raise HTTPException(status_code=500, detail="checkin_error")
        return {"ok": True}

    # ── 시설 찾기(실데이터: DATA_GO_KR_KEY 있으면 실, 없으면 데모) ──
    @app.post("/facilities")
    def facilities(req: FacilitiesReq, sub: dict = Depends(get_subject)):
        kind = req.kind if req.kind in ("pharmacy", "hospital") else "pharmacy"
        res = {"supported": False}
        try:
            import kr_facilities as kf
            res = kf.find_real(kind, req.lat, req.lon)
        except Exception:
            res = {"supported": False}
        if res.get("supported"):
            return {"real": bool(res.get("real", True)), "kind": kind,
                    "items": res.get("items", []), "source": res.get("source"),
                    "notice": res.get("notice")}
        try:                                    # 데모 폴백(키 미설정/미인가)
            import facility_finder as ff
            demo = ff.find_demo(kind, "서울")
            return {"real": False, "kind": kind, "items": demo.get("items", []),
                    "notice": "데모 데이터(실데이터 키 미설정/위치 권한 필요)"}
        except Exception:
            return {"real": False, "kind": kind, "items": [],
                    "notice": "데이터를 불러오지 못했습니다"}

    # ── 페르소나(데모 개인화 체험) ───────────────────────────
    @app.get("/personas")
    def personas_list():
        return {"personas": [{"id": p.get("id"), "name": p.get("name"), "emoji": p.get("emoji", ""),
                              "profile": p.get("profile", ""), "tags": p.get("tags", []),
                              "samples": (p.get("sample_queries") or [])[:2]} for p in _load_personas()]}

    @app.post("/persona/select")
    def persona_select(req: PersonaReq, sub: dict = Depends(get_subject)):
        p = _persona(req.persona_id)
        if not p:
            raise HTTPException(status_code=404, detail="unknown_persona")
        import account_db
        account_db.set_persona(sub["subject_id"], req.persona_id)
        # 페르소나 선택 = 합성 건강프로필로 개인화 체험 동의 → 민감정보 grant(데모)
        consent_db.record_consent(sub["subject_id"], "sensitive_info", "grant", source="persona_select")
        return {"ok": True, "persona_id": req.persona_id, "name": p.get("name"), "band": _persona_band(p)}

    @app.get("/persona")
    def persona_get(sub: dict = Depends(get_subject)):
        import account_db
        p = _persona(account_db.get_persona(sub["subject_id"]))
        if not p:
            return {"persona": None}
        return {"persona": {"id": p.get("id"), "name": p.get("name"), "emoji": p.get("emoji", ""),
                            "profile": p.get("profile", ""), "band": _persona_band(p),
                            "samples": (p.get("sample_queries") or [])}}

    # ── 루틴형 전환(12주 프로그램) 라우트 — 정본 docs/plan/25 ──────
    # 등록 실패가 기존 앱 부팅을 막지 않게 방어(루틴은 additive).
    try:
        from . import routine_routes

        def _persona_of(sid):
            import account_db as _ad
            return _persona(_ad.get_persona(sid))

        def _consent_ok(sid):
            recs = consent_db.get_records(sid)
            return consent_db.granted_items(recs), consent_db.personalization_allowed(recs)

        routine_routes.register(app, {
            "get_subject": get_subject,
            "persona_of": _persona_of,
            "band_of": _persona_band,
            "consent_ok": _consent_ok,
        })
    except Exception as _e:                     # noqa: BLE001 — 부팅 우선
        import logging
        logging.getLogger(__name__).warning("routine routes 등록 실패: %s", _e)

    return app


app = create_app()
