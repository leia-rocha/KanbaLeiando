"""Sessao comum: ativacao de primeiro acesso e recuperacao (RF03, RF04)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.deps import get_repo, get_request_id
from app.repositories import Repo
from app.schemas.auth import (
    ActivateRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    MeResponse,
)
from app.schemas.common import UserStatus
from app.services import authorization as authz
from app.services import email as email_service

router = APIRouter(prefix="/auth")


@router.post("/activate", response_model=MeResponse)
def activate(
    _body: ActivateRequest,
    authorization: str | None = Header(default=None),
    repo: Repo = Depends(get_repo),
) -> MeResponse:
    """Conclui o primeiro acesso: exige auth recente por password e mesmo UID."""
    uid, profile = authz.resolve_activation_identity(repo, authorization)
    from google.cloud import firestore

    repo.user_ref(uid).update(
        {"status": UserStatus.ACTIVE.value, "updatedAt": firestore.SERVER_TIMESTAMP}
    )
    updated = repo.user_ref(uid).get().to_dict() or {}
    return MeResponse(
        uid=uid,
        email=updated.get("email", profile.get("email", "")),
        name=updated.get("name", profile.get("name", "")),
        status=UserStatus.ACTIVE,
    )


@router.post("/forgot-password", response_model=GenericMessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    repo: Repo = Depends(get_repo),
    _rid: str = Depends(get_request_id),
) -> GenericMessageResponse:
    """Resposta publica generica para e-mail cadastrado ou nao (RF04)."""
    from app.utils.text import normalize_email

    norm = normalize_email(body.email)
    matches = list(
        repo.db.collection("users").where("normalizedEmail", "==", norm).limit(1).stream()
    )
    if matches:
        profile = matches[0].to_dict() or {}
        try:
            email_service.send_password_reset_email(
                profile.get("name", ""), profile.get("email", "")
            )
        except Exception:  # noqa: BLE001 - nunca revela existencia por erro
            pass
    return GenericMessageResponse()
