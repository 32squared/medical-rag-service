"""BFF 요청/응답 Pydantic 모델 — OpenAPI 자동생성 → 프론트 openapi-typescript."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PassStartReq(BaseModel):
    return_url: Optional[str] = None


class PassStartResp(BaseModel):
    tx_id: str
    provider: str
    redirect_url: str
    mock: bool


class PassCallbackReq(BaseModel):
    tx_id: str
    mock_identity: Optional[str] = None   # mock provider 전용(실연동 시 무시)


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    session_id: str
    subject_id: str


class RefreshReq(BaseModel):
    session_id: str
    refresh_token: str


class AccessResp(BaseModel):
    access_token: str


class ConsentItemView(BaseModel):
    item_key: str
    title: str
    required: bool
    granted: bool


class ConsentReq(BaseModel):
    item_key: str
    action: str            # grant | revoke
    item_version: int = 1
    source: str = "settings"


class ConsentHistoryRow(BaseModel):
    item_key: str
    action: str
    source: Optional[str] = None
    created_at: str


class MeResp(BaseModel):
    subject_id: str
    status: str
    consent: List[ConsentItemView]
    missing_required: List[str]


class ChatReq(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    cross_border: bool = False   # 국외 LLM 경로 여부(개인화 게이트에 cross_border 동의 필요)


class ChatResp(BaseModel):
    personalization: bool
    rag: dict
