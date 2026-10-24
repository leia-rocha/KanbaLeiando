"""Uploads, download e previa de anexos (secao 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.context import CurrentUser
from app.deps import get_current_user, get_repo
from app.errors import ForbiddenError
from app.repositories import Repo
from app.schemas.attachment import (
    PreviewResponse,
    SignedUrlResponse,
    UploadCompleteResponse,
    UploadCreateRequest,
    UploadCreateResponse,
)
from app.services import attachments as attach_service
from app.services import authorization as authz

router = APIRouter()


@router.post("/boards/{board_id}/uploads", response_model=UploadCreateResponse)
def create_upload(
    board_id: str,
    body: UploadCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    repo: Repo = Depends(get_repo),
):
    authz.require_board_editor(repo, board_id, user)
    data = attach_service.create_upload_session(
        repo, user.uid, board_id,
        field_id=body.fieldId, draft_id=body.draftId, card_id=body.cardId,
        original_name=body.originalName, expected_size=body.expectedSize,
        content_type=body.contentType,
    )
    return UploadCreateResponse(**data)


@router.post("/uploads/{upload_id}/complete", response_model=UploadCompleteResponse)
def complete_upload(
    upload_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repo = Depends(get_repo),
):
    data = attach_service.complete_upload(repo, user.uid, upload_id)
    return UploadCompleteResponse(**data)


@router.delete("/uploads/{upload_id}", status_code=204)
def cancel_upload(
    upload_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: Repo = Depends(get_repo),
):
    attach_service.cancel_upload(repo, user.uid, upload_id)


def _authorize_attachment_read(
    repo: Repo, board_id: str, user, visitor
) -> None:
    """Membro autenticado OU leitor publico valido do mesmo quadro."""
    if user is not None:
        authz.require_board_editor(repo, board_id, user)
        return
    if visitor is not None and visitor.board_id == board_id:
        return
    raise ForbiddenError("Sem acesso ao anexo.")


@router.get(
    "/boards/{board_id}/cards/{card_id}/attachments/{attachment_id}/download",
    response_model=SignedUrlResponse,
)
def download_attachment(
    board_id: str,
    card_id: str,
    attachment_id: str,
    repo: Repo = Depends(get_repo),
    authorization: str | None = Header(default=None),
):
    # Resolve membro ou visitante a partir do header, aceitando ambos.
    user, visitor = _resolve_reader(repo, authorization)
    _authorize_attachment_read(repo, board_id, user, visitor)
    att = authz.assert_attachment_in_card(repo, board_id, card_id, attachment_id)
    return SignedUrlResponse(**attach_service.signed_download_url(repo, board_id, card_id, att))


@router.get(
    "/boards/{board_id}/cards/{card_id}/attachments/{attachment_id}/preview",
    response_model=PreviewResponse,
)
def preview_attachment(
    board_id: str,
    card_id: str,
    attachment_id: str,
    repo: Repo = Depends(get_repo),
    authorization: str | None = Header(default=None),
):
    user, visitor = _resolve_reader(repo, authorization)
    _authorize_attachment_read(repo, board_id, user, visitor)
    att = authz.assert_attachment_in_card(repo, board_id, card_id, attachment_id)
    descriptor = attach_service.preview_descriptor(att)
    signed = attach_service.signed_download_url(repo, board_id, card_id, att)
    kind = descriptor["kind"]
    if kind in ("image", "pdf"):
        return PreviewResponse(status="ready", kind=kind, url=signed["url"])
    if kind == "pages":
        # Conversao Office sob demanda e tratada pelo servico de previa pesada.
        return PreviewResponse(
            status="processing", kind="pages",
            reason="Conversao sob demanda; recarregue em instantes.",
        )
    return PreviewResponse(status="ready", kind="download", url=signed["url"])


def _resolve_reader(repo: Repo, authorization: str | None):
    """Tenta resolver como membro; se for credencial publica, resolve visitante."""
    try:
        user = authz.resolve_current_user(repo, authorization)
        return user, None
    except Exception:  # noqa: BLE001
        pass
    try:
        visitor = authz.resolve_public_visitor(repo, authorization)
        return None, visitor
    except Exception:  # noqa: BLE001
        return None, None
