"""Contratos de compartilhamento, link publico e auditoria (secoes 10-11)."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import MemberRole, StrictModel


class MemberGrantRequest(StrictModel):
    email: EmailStr
    idempotencyKey: str | None = Field(default=None, max_length=200)


class MemberOut(StrictModel):
    uid: str
    name: str
    email: EmailStr
    role: MemberRole
    grantedAt: str


class MemberListResponse(StrictModel):
    members: list[MemberOut]
    ownerUid: str


class GrantResponse(StrictModel):
    message: str
    member: MemberOut | None = None
    # Quando o e-mail nao e cadastrado, orienta sem criar convite (DT04).
    guidance: str | None = None


class PublicLinkOut(StrictModel):
    enabled: bool
    url: str | None = None
    shareVersion: int


class PublicSessionRequest(StrictModel):
    boardId: str
    token: str


class PublicSessionResponse(StrictModel):
    customToken: str
    boardId: str
    shareVersion: int
    scope: str = "public_view"


class AuditEventOut(StrictModel):
    eventId: str
    action: str
    entityType: str
    entityId: str
    actorUid: str
    actorNameSnapshot: str
    occurredAt: str
    requestId: str
    changedFields: dict | None = None


class AuditListResponse(StrictModel):
    events: list[AuditEventOut]
    nextCursor: str | None = None
