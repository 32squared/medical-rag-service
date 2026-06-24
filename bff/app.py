"""
마이헬스케어 P0 BFF (FastAPI) — 인증·동의검증·라우팅·RAG 프록시.

정본: docs/plan/23-p0-detailed-design.md §4. 모든 개인화/방향2 게이트는 동의원장
(consent_db)을 진실원천으로 판정 → RAG 에 헤더만 전달(원시값·진단명 미전달).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query

import account_db
import consent_db

from . import pass_adapter, rag_client
from .models import (
    AccessResp,
    ChatReq,
    ChatResp,
    ConsentReq,
    MeResp,
    PassCallbackReq,
    PassStartReq,
    PassStartResp,
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


def get_subject(authorization: Optional[str] = Header(None)) -> dict:
    """Bearer access 토큰 → {subject_id, session_id}. 위조·만료·세션철회를 거부(401)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    payload = verify_access_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="invalid_token")
    sid = payload.get("sid")
    # 세션 활성 확인 → 로그아웃·탈퇴·만료가 access 토큰을 즉시 무효화
    if sid is not None and account_db.get_active_session(sid) is None:
        raise HTTPException(status_code=401, detail="session_revoked")
    return {"subject_id": payload.get("sub"), "session_id": sid}


def create_app() -> FastAPI:
    app = FastAPI(title="마이헬스케어 BFF", version="0.1.0")

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
        ci_hash = account_db.hash_ci(identity.get("ci") or "")
        di_hash = account_db.hash_ci(identity.get("di") or "")
        account_id = account_db.upsert_account_by_ci(ci_hash, di_hash=di_hash)
        if not account_id:
            raise HTTPException(status_code=500, detail="account_error")
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
        token = issue_access_token(sess["subject_id"], session_id=req.session_id)
        return {"access_token": token}

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
        account_db.withdraw_account(sub["subject_id"])  # 이력 보존, status=withdrawn
        return {"ok": True}

    # ── 의료 채팅(RAG 프록시) ────────────────────────────────
    @app.post("/chat", response_model=ChatResp)
    def chat(req: ChatReq, sub: dict = Depends(get_subject)):
        records = consent_db.get_records(sub["subject_id"])
        if "personal_info" not in consent_db.granted_items(records):
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        personalize = consent_db.personalization_allowed(
            records, cross_border_needed=req.cross_border)
        rag = rag_client.chat(
            req.message, conversation_id=req.conversation_id,
            personalization=personalize, cross_border_ack=req.cross_border)
        return {"personalization": personalize, "rag": rag}

    @app.get("/home")
    def home(sub: dict = Depends(get_subject)):
        records = consent_db.get_records(sub["subject_id"])
        if "personal_info" not in consent_db.granted_items(records):
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        return {"cards": [], "personalization": consent_db.personalization_allowed(records)}

    return app


app = create_app()
