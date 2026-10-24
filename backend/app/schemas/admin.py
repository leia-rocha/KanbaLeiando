"""Contratos do painel administrativo (secao 3.3, 14.1)."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import StrictModel, UserStatus


class AdminLoginRequest(StrictModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=400)


class AdminSessionResponse(StrictModel):
    message: str = "Sessao administrativa iniciada."
    csrfToken: str
    expiresAt: str


class AdminUserOut(StrictModel):
    uid: str
    name: str
    email: EmailStr
    status: UserStatus
    createdAt: str
    updatedAt: str
    lastWelcomeState: str | None = None


class AdminUserListResponse(StrictModel):
    users: list[AdminUserOut]
    nextCursor: str | None = None


class AdminUserCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr


class AdminUserPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    status: UserStatus | None = None  # permite desativar/reativar


class AdminActionResponse(StrictModel):
    message: str
    emailState: str | None = None
    operationId: str | None = None
