"""bff/metrics_routes.py — 오늘의 나 재미 레이어 BFF 라우트.

정본: docs/design/todays-me-mockups/02-dev-requirements.md §4 (API 계약) · §6 (밴드 게이팅).

경로
  PUT  /metrics/today            일일 지표 입력(물·걸음 수동·마음챙김 세션·취침)
  POST /metrics/steps/sync       걸음 자동 연동값 전달(네이티브 래퍼 단계용, 지금은 수동값과 동일 경로)
  GET  /metrics/day?date=        화면 2 페이로드(링·지표 행·환산·하이라이트·CTA)
  GET  /archetype/day?date=      화면 3 페이로드(아키타입·태그·희귀도·7일 컬렉션)
  POST /archetype/seen           리빌 봤음 표시(재진입 시 연출 생략)
  GET  /wellness-type/quiz · POST /wellness-type/quiz · GET/PUT /wellness-type
  POST /card · GET /card/{id} · PATCH /card/{id} · GET /card/list?month=

원칙
  - 모든 응답에 검진 수치·밴드 라벨·구간·미완료 개수·타 사용자 비교값을 싣지 않는다(FR-C09).
  - 경고·응급 밴드: 지표 입력은 허용, 아키타입·카드·컬렉션은 403 band_gate(FR-C05).
  - 아키타입·환산·하이라이트·연속 문구는 **서버가 최종 문자열로** 내린다(FR-T2-03).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import archetype_engine as ae
import metrics_repo as mr
import routine_repo as rr


# ── 요청 모델 ────────────────────────────────────────────────
class MetricsReq(BaseModel):
    water_cups: Optional[int] = None
    steps: Optional[int] = None
    steps_source: Optional[str] = None      # manual | auto
    steps_confirmed: Optional[bool] = None
    mind_session_completed: Optional[bool] = None
    mind_seconds: Optional[int] = None      # 세션 길이(기본 60)
    bedtime_at: Optional[str] = None        # ISO
    client_ts: Optional[str] = None
    idempotency_key: Optional[str] = None


class StepsSyncReq(BaseModel):
    steps: int
    synced_at: Optional[str] = None
    client_ts: Optional[str] = None


class SeenReq(BaseModel):
    date: Optional[str] = None


class QuizReq(BaseModel):
    answers: List[int]


class TypeReq(BaseModel):
    type_id: str


class CardCreateReq(BaseModel):
    date: Optional[str] = None


class CardPatchReq(BaseModel):
    theme_id: Optional[str] = None
    stickers: Optional[List[Dict]] = None
    comment: Optional[str] = None
    hide_numbers: Optional[bool] = None


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ══════════════════════════ 공용 블록(홈 1콜에서도 사용) ══════════════════════════
def fun_blocks(sid: str, band: Optional[str], date: Optional[str] = None) -> Dict:
    """GET /routine/today 에 얹는 `safety.fun_layer` · `tracks` · `archetype` 블록(§4-1)."""
    date = date or rr.today_kst()
    allowed = ae.fun_layer_allowed(band)
    m = _safe(lambda: mr.get_day(sid, date)) or {}
    st = ae.track_state(m)
    if not allowed:
        for t in st.values():             # 경고 밴드: 완료 뱃지·깨어남 연출 숨김(FR-T1-09)
            t["awake"] = False
            t["complete"] = False
        return {"fun_layer": False, "tracks": st, "archetype": None}
    tracks = ae.completed_tracks(m)
    aid = ae.archetype_for(tracks)
    seen = bool((_safe(lambda: mr.get_archetype(sid, date)) or {}).get("reveal_seen_at")) if aid else False
    return {"fun_layer": True, "tracks": st,
            "archetype": {"preview": aid, "completed_count": len(tracks), "seen_today": seen}}


def _recompute(sid: str, band: Optional[str], date: str) -> Optional[str]:
    """지표 변경 후 아키타입 재계산·저장. 경고 밴드는 결과를 만들지 않는다."""
    m = _safe(lambda: mr.get_day(sid, date)) or {}
    if not ae.fun_layer_allowed(band):
        _safe(lambda: mr.set_archetype(sid, date, None, []))
        return None
    tracks = ae.completed_tracks(m)
    aid = ae.archetype_for(tracks)
    prev = _safe(lambda: mr.get_archetype(sid, date)) or {}
    rarity = prev.get("rarity_pct")
    if aid and aid != prev.get("archetype_id"):
        rarity = _rarity_for(aid, date)
    _safe(lambda: mr.set_archetype(sid, date, aid, tracks, rarity))
    return aid


def _rarity_for(aid: str, date: str) -> Optional[int]:
    stat = _safe(lambda: mr.monthly_stat(date[:7], aid))
    if not stat:
        return None
    return ae.rarity_pct(stat.get("user_count"), stat.get("denominator"))


def _streak_text(sid: str, band: Optional[str]) -> str:
    """행동 카드 체크인 기준 연속 일수(C6). 경고 밴드는 '오늘 기록이 남았어요'."""
    if not ae.fun_layer_allowed(band):
        return "오늘 기록이 남았어요"
    dates = _safe(lambda: rr.done_dates(sid), []) or []
    n = _safe(lambda: rr.streak_from(dates), 0) or 0
    return f"{n}일째 이어졌어요" if n >= 2 else "기록이 남았어요"


# ══════════════════════════ 등록 ══════════════════════════
def register(app, deps: Dict) -> None:
    get_subject = deps["get_subject"]
    persona_of = deps["persona_of"]
    band_of = deps["band_of"]
    consent_ok = deps["consent_ok"]

    def _ctx(sid: str):
        persona = _safe(lambda: persona_of(sid))
        band = _safe(lambda: band_of(persona)) if persona else None
        granted, _ = _safe(lambda: consent_ok(sid), (set(), False))
        if "personal_info" not in (granted or set()):
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        return band

    def _gate(band: Optional[str]) -> None:
        if not ae.fun_layer_allowed(band):
            raise HTTPException(status_code=403, detail="band_gate")

    def _date_arg(date: Optional[str]) -> str:
        d = (date or rr.today_kst())[:10]
        if rr.days_between(d, rr.today_kst()) < 0:
            raise HTTPException(status_code=400, detail="future_date")
        return d

    # ── 일일 지표 ─────────────────────────────────────────
    @app.put("/metrics/today")
    def metrics_today(req: MetricsReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        applied = ae.applied_date(req.client_ts)
        fields: Dict = {"band_snapshot": band}

        if req.water_cups is not None:
            if not (0 <= int(req.water_cups) <= 8):
                raise HTTPException(status_code=400, detail="invalid_value")
            fields["water_cups"] = int(req.water_cups)
        if req.steps is not None:
            if not (0 <= int(req.steps) <= 200000):
                raise HTTPException(status_code=400, detail="invalid_value")
            fields["steps"] = int(req.steps)
            fields["steps_source"] = req.steps_source if req.steps_source in ("manual", "auto") else "manual"
            fields["steps_synced_at"] = rr.now_iso()
            if req.steps_confirmed is not None:
                fields["steps_confirmed"] = 1 if req.steps_confirmed else 0
        elif req.steps_confirmed is not None:
            fields["steps_confirmed"] = 1 if req.steps_confirmed else 0

        row = _safe(lambda: mr.upsert_day(sid, applied, **fields))
        if row is None:
            raise HTTPException(status_code=500, detail="metrics_error")

        if req.mind_session_completed:
            secs = int(req.mind_seconds) if req.mind_seconds else 60
            if secs < 60:
                raise HTTPException(status_code=400, detail="invalid_value")   # 완주(60초)만 세션
            _safe(lambda: mr.add_mind_session(sid, applied, secs))

        if req.bedtime_at:
            bd = ae.bedtime_metric_date(req.bedtime_at)
            if not bd:
                raise HTTPException(status_code=400, detail="invalid_value")
            _safe(lambda: mr.upsert_day(sid, bd, bedtime_at=req.bedtime_at, band_snapshot=band))

        _recompute(sid, band, applied)
        _safe(lambda: __import__("analytics_events").emit("track_input", track=None))
        blocks = fun_blocks(sid, band, applied)
        return {"ok": True, "applied_date": applied, **blocks}

    @app.post("/metrics/steps/sync")
    def metrics_steps_sync(req: StepsSyncReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        applied = ae.applied_date(req.client_ts)
        if req.steps < 0 or req.steps > 200000:
            raise HTTPException(status_code=400, detail="invalid_value")
        cur = _safe(lambda: mr.get_day(sid, applied)) or {}
        if (cur.get("steps_source") == "manual") and int(cur.get("steps_confirmed") or 0):
            pass                                   # 수동 확정값은 자동값이 덮지 않는다
        else:
            _safe(lambda: mr.upsert_day(sid, applied, steps=int(req.steps), steps_source="auto",
                                        steps_synced_at=req.synced_at or rr.now_iso(), band_snapshot=band))
        _recompute(sid, band, applied)
        return {"ok": True, "applied_date": applied, **fun_blocks(sid, band, applied)}

    @app.get("/metrics/day")
    def metrics_day(date: Optional[str] = None, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        d = _date_arg(date)
        today = rr.today_kst()
        m = _safe(lambda: mr.get_day(sid, d)) or {}
        allowed = ae.fun_layer_allowed(band)
        tracks = ae.completed_tracks(m) if allowed else []
        hist = [h for h in (_safe(lambda: mr.last_days(sid, d, 7), []) or []) if h.get("metric_date") != d]
        record_days = len([h for h in hist + ([m] if m else [])
                           if ae.track_state(h)["water"]["awake"] or ae.track_state(h)["steps"]["awake"]
                           or ae.track_state(h)["mind"]["awake"]])
        seen = bool((_safe(lambda: mr.get_archetype(sid, d)) or {}).get("reveal_seen_at"))
        if not allowed:
            cta = "weekly_report"
        elif not tracks:
            cta = "go_today"
        elif seen:
            cta = "reveal_replay"
        else:
            cta = "reveal"
        return {
            "date": d, "is_today": d == today, "is_past": d != today,
            "fun_layer": allowed,
            "completed_count": len(tracks),
            "tracks": {"diet": "done" if "diet" in tracks else "rest",
                       "exercise": "done" if "exercise" in tracks else "rest",
                       "habit": "done" if "habit" in tracks else "rest"},
            "metrics": ae.metrics_rows(m),
            "highlight": ae.highlight(m, hist, record_days) if allowed else None,
            "streak_text": _streak_text(sid, band),
            "cta": cta,
        }

    # ── 아키타입·리빌 ─────────────────────────────────────
    @app.get("/archetype/day")
    def archetype_day(date: Optional[str] = None, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        d = _date_arg(date)
        row = _safe(lambda: mr.get_archetype(sid, d))
        if not row:
            aid = _recompute(sid, band, d)
            row = _safe(lambda: mr.get_archetype(sid, d)) if aid else None
        if not row:
            raise HTTPException(status_code=404, detail="no_archetype")
        info = ae.archetype_info(row["archetype_id"]) or {}
        m = _safe(lambda: mr.get_day(sid, d)) or {}
        rar = row.get("rarity_pct")
        return {
            "date": d, **info,
            "tags": ae.why_tags(m, row.get("completed_tracks") or []),
            "rarity_pct": rar, "rarity_text": ae.rarity_text(rar),
            "seen_today": bool(row.get("reveal_seen_at")),
            "collection_last7": _safe(lambda: mr.collection(sid, d, 7), []) or [],
        }

    @app.post("/archetype/seen")
    def archetype_seen(req: SeenReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        d = _date_arg(req.date)
        ts = _safe(lambda: mr.mark_seen(sid, d))
        return {"ok": bool(ts), "reveal_seen_at": ts}

    # ── 웰니스 타입 ───────────────────────────────────────
    @app.get("/wellness-type/quiz")
    def wellness_quiz(sub: dict = Depends(get_subject)):
        return {"questions": [
            {"id": q["id"], "text": q["text"],
             "options": [{"index": i, "label": o, "type_id": ae._TYPE_ORDER[i]}
                         for i, o in enumerate(q["options"])]}
            for q in ae.WELLNESS_QUIZ]}

    def _type_payload(sid: str) -> Dict:
        row = _safe(lambda: mr.get_wellness_type(sid)) or {}
        info = ae.wellness_type_info(row.get("type_id"))
        if not info:
            return {"type_id": None}
        return {**info, "assigned_by": row.get("assigned_by"), "assigned_at": row.get("assigned_at")}

    @app.post("/wellness-type/quiz")
    def wellness_quiz_submit(req: QuizReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        tid = ae.assign_wellness_type(req.answers)
        if not tid:
            raise HTTPException(status_code=400, detail="invalid_answers")
        _safe(lambda: mr.set_wellness_type(sid, tid, "onboarding", req.answers))
        _safe(lambda: __import__("analytics_events").emit("wellness_quiz_complete", type_id=tid))
        return _type_payload(sid)

    @app.get("/wellness-type")
    def wellness_type_get(sub: dict = Depends(get_subject)):
        return _type_payload(sub["subject_id"])

    @app.put("/wellness-type")
    def wellness_type_put(req: TypeReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        if req.type_id not in ae.WELLNESS_TYPES:
            raise HTTPException(status_code=400, detail="unknown_type")
        prev = (_safe(lambda: mr.get_wellness_type(sid)) or {}).get("type_id")
        _safe(lambda: mr.set_wellness_type(sid, req.type_id, "user"))
        _safe(lambda: __import__("analytics_events").emit("wellness_type_change", type_id=req.type_id))
        return {**_type_payload(sid), "previous": prev}

    # ── 공유 카드 ─────────────────────────────────────────
    def _card_out(sid: str, card: Dict, band: Optional[str]) -> Dict:
        wt = (_safe(lambda: mr.get_wellness_type(sid)) or {}).get("type_id")
        m = _safe(lambda: mr.get_day(sid, card["metric_date"])) or {}
        payload = ae.build_card_payload(
            metric_date=card["metric_date"], m=m, archetype_id=card["archetype_id"],
            rarity=card.get("rarity_pct"), theme_id=card.get("theme_id") or "coral",
            stickers=card.get("stickers_json") or [], comment=card.get("comment"),
            hide_numbers=bool(card.get("hide_numbers")), wellness_type_id=wt, band=band)
        locked = rr.now_iso() >= (card.get("locked_at") or "")
        return {"card_id": card["card_id"], "date": card["metric_date"], "payload": payload,
                "locked_at": card.get("locked_at"), "locked": locked}

    @app.post("/card")
    def card_create(req: CardCreateReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        d = _date_arg(req.date)
        row = _safe(lambda: mr.get_archetype(sid, d))
        if not row:
            raise HTTPException(status_code=404, detail="no_archetype")
        wt = (_safe(lambda: mr.get_wellness_type(sid)) or {}).get("type_id")
        theme = (ae.wellness_type_info(wt) or {}).get("default_theme") or "coral"
        m = _safe(lambda: mr.get_day(sid, d)) or {}
        snap = {"metrics": [{"kind": r["kind"], "value": r["value"]} for r in ae.metrics_rows(m)[:3]]}
        card = _safe(lambda: mr.create_card(sid, d, row["archetype_id"], theme, snap,
                                            row.get("rarity_pct"), ae.card_lock_at(d)))
        if not card:
            raise HTTPException(status_code=500, detail="card_error")
        _safe(lambda: __import__("analytics_events").emit("card_saved_to_dex", archetype_id=row["archetype_id"]))
        return _card_out(sid, card, band)

    @app.get("/card/list")
    def card_list(month: Optional[str] = None, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        return {"cards": _safe(lambda: mr.list_cards(sid, month), []) or []}

    @app.get("/card/{card_id}")
    def card_get(card_id: str, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        card = _safe(lambda: mr.get_card(card_id))
        if not card or card.get("subject_id") != sid:
            raise HTTPException(status_code=404, detail="no_card")
        return _card_out(sid, card, band)

    @app.patch("/card/{card_id}")
    def card_patch(card_id: str, req: CardPatchReq, sub: dict = Depends(get_subject)):
        sid = sub["subject_id"]
        band = _ctx(sid)
        _gate(band)
        card = _safe(lambda: mr.get_card(card_id))
        if not card or card.get("subject_id") != sid:
            raise HTTPException(status_code=404, detail="no_card")
        if rr.now_iso() >= (card.get("locked_at") or ""):
            raise HTTPException(status_code=409, detail="locked")
        if req.theme_id is not None and req.theme_id not in ae.CARD_THEMES:
            raise HTTPException(status_code=422, detail="unknown_theme")
        if req.stickers is not None:
            err = ae.validate_stickers(req.stickers)
            if err:
                raise HTTPException(status_code=422, detail=err)
        clear = False
        if req.comment is not None:
            c = req.comment.strip()
            if len(c) > ae.CARD_COMMENT_MAX:
                raise HTTPException(status_code=422, detail="comment_too_long")
            if c == "":
                clear = True
        updated = _safe(lambda: mr.update_card(card_id, theme_id=req.theme_id, stickers=req.stickers,
                                               comment=(None if clear else req.comment),
                                               hide_numbers=req.hide_numbers, clear_comment=clear))
        if not updated:
            raise HTTPException(status_code=500, detail="card_error")
        return _card_out(sid, updated, band)
