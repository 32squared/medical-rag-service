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
        return {"ok": True}

    # ── 의료 채팅(RAG 프록시) ────────────────────────────────
    @app.post("/chat", response_model=ChatResp)
    def chat(req: ChatReq, sub: dict = Depends(get_subject)):
        records = consent_db.get_records(sub["subject_id"])
        granted = consent_db.granted_items(records)
        if "personal_info" not in granted:
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        personalize = consent_db.personalization_allowed(
            records, cross_border_needed=req.cross_border)
        # 국외이전 ack 는 **원장 기준**으로만 1 — 클라이언트 flag 만으로 국외경로 신호를
        # 보내지 않음(cross_border 동의 없으면 ack=0, 원문 국외 라우팅 차단).
        cross_border_ack = bool(req.cross_border) and ("cross_border" in granted)
        rag = rag_client.chat(
            req.message, conversation_id=req.conversation_id,
            personalization=personalize, cross_border_ack=cross_border_ack)
        return {"personalization": personalize, "rag": rag}

    @app.get("/home")
    def home(sub: dict = Depends(get_subject)):
        records = consent_db.get_records(sub["subject_id"])
        if "personal_info" not in consent_db.granted_items(records):
            raise HTTPException(status_code=403, detail="personal_info_consent_required")
        return {"cards": [], "personalization": consent_db.personalization_allowed(records)}

    return app


app = create_app()
