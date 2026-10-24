"""Contratos de sessao comum, ativacao e recuperacao (secao 3, 14.1)."""

from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import StrictModel, UserStatus


class PublicConfig(StrictModel):
    """Resposta de GET /config: somente valores publicos (secao 15.3)."""

    firebaseApiKey: str
    firebaseAuthDomain: str
    firebaseProjectId: str
    firebaseAppId: str
    appTimezone: str
    maxUploadBytes: int
    appEnv: str
    usingEmulators: bool
    firestoreEmulatorHost: str | None = None
    authEmulatorHost: str | None = None


class MeResponse(StrictModel):
    uid: str
    name: str
    email: EmailStr
    status: UserStatus


class ActivateRequest(StrictModel):
    """POST /auth/activate: conclui o primeiro acesso (RF03)."""

    # O ID token vem no header Authorization; nada de UID/status pelo cliente.
    confirm: bool = True


class ForgotPasswordRequest(StrictModel):
    email: EmailStr


class GenericMessageResponse(StrictModel):
    message: str = Field(default="Se o e-mail estiver cadastrado, enviaremos instrucoes.")
