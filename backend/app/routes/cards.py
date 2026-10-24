"""Cards, campos e modelos (RF17-RF26)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_repo, get_request_id
from app.repositories import Repo
from app.schemas.board import (
    CardCreate,
    CardDetailOut,
    CardDuplicateRequest,
    CardMoveRequest,
    CardSaveRequest,
    TemplateCreate,
    TemplateOut,
    TemplatePatch,
)
from app.services import cards as card_service
from app.services import templates as template_service

router = APIRouter(prefix="/boards/{board_id}")


@router.post("/cards", response_model=CardDetailOut)
def create_card(
    board_id: str,
    body: CardCreate,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = card_service.create_card(
        repo, user, board_id, body.title, body.columnId, body.templateId, rid, body.idempotencyKey
    )
    return CardDetailOut(**data)


@router.get("/cards/{card_id}", response_model=CardDetailOut)
def get_card(
    board_id: str, card_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)
):
    from app.services import authorization as authz

    authz.require_board_editor(repo, board_id, user)
    return CardDetailOut(**card_service.get_card_detail(repo, user, board_id, card_id))


@router.patch("/cards/{card_id}", response_model=CardDetailOut)
def save_card(
    board_id: str,
    card_id: str,
    body: CardSaveRequest,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    fields = [f.model_dump() for f in body.fields]
    data = card_service.save_card_detail(
        repo, user, board_id, card_id, body.title, fields, body.contentVersion, rid
    )
    return CardDetailOut(**data)


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(
    board_id: str,
    card_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    card_service.delete_card(repo, user, board_id, card_id, rid)


@router.post("/cards/{card_id}/move", response_model=CardDetailOut)
def move_card(
    board_id: str,
    card_id: str,
    body: CardMoveRequest,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = card_service.move_card(
        repo, user, board_id, card_id, body.targetColumnId,
        body.beforeCardId, body.afterCardId, body.positionVersion, rid,
    )
    return CardDetailOut(**data)


@router.post("/cards/{card_id}/duplicate", response_model=CardDetailOut)
def duplicate_card(
    board_id: str,
    card_id: str,
    body: CardDuplicateRequest,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = card_service.duplicate_card(repo, user, board_id, card_id, rid, body.idempotencyKey)
    return CardDetailOut(**data)


# ------- Modelos -------


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)
):
    return [TemplateOut(**t) for t in template_service.list_templates(repo, user, board_id)]


@router.post("/templates", response_model=TemplateOut)
def create_template(
    board_id: str,
    body: TemplateCreate,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = template_service.create_template(
        repo, user, board_id, body.name, body.fromCardId, body.replaceExisting, rid
    )
    return TemplateOut(**data)


@router.patch("/templates/{template_id}", response_model=TemplateOut)
def rename_template(
    board_id: str,
    template_id: str,
    body: TemplatePatch,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = template_service.rename_template(
        repo, user, board_id, template_id, body.name, body.baseVersion, rid
    )
    return TemplateOut(**data)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    board_id: str,
    template_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    template_service.delete_template(repo, user, board_id, template_id, rid)
