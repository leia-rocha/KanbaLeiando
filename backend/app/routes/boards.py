"""Kanbans e colunas (RF12-RF16, secao 14.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_repo, get_request_id
from app.repositories import Repo
from app.schemas.board import (
    BoardCreate,
    BoardListResponse,
    BoardOut,
    BoardPatch,
    BoardSummaryOut,
    CardSummaryOut,
    ColumnCreate,
    ColumnOut,
    ColumnPatch,
    ColumnReorder,
)
from app.services import boards as board_service
from app.services import cards as card_service
from app.services import operations

router = APIRouter(prefix="/boards")


@router.get("", response_model=BoardListResponse)
def list_boards(user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    data = board_service.list_boards(repo, user)
    return BoardListResponse(boards=[BoardSummaryOut(**b) for b in data["boards"]])


@router.post("", response_model=BoardOut)
def create_board(
    body: BoardCreate,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = board_service.create_board(repo, user, body.name, rid, body.idempotencyKey)
    return BoardOut(**data)


@router.get("/{board_id}", response_model=BoardOut)
def get_board(board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    return BoardOut(**board_service.get_board(repo, user, board_id))


@router.patch("/{board_id}", response_model=BoardOut)
def rename_board(
    board_id: str,
    body: BoardPatch,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    return BoardOut(
        **board_service.rename_board(repo, user, board_id, body.name, body.baseVersion, rid)
    )


@router.delete("/{board_id}", status_code=202)
def delete_board(
    board_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
):
    from app.services import authorization as authz

    authz.require_board_owner(repo, board_id, user)
    op_id = operations.start_board_deletion(repo, board_id, user.uid)
    return {"message": "Exclusao iniciada.", "operationId": op_id}


# ------- Colunas -------


@router.get("/{board_id}/columns", response_model=list[ColumnOut])
def list_columns(board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    return [ColumnOut(**c) for c in board_service.list_columns(repo, user, board_id)]


@router.post("/{board_id}/columns", response_model=ColumnOut)
def create_column(
    board_id: str,
    body: ColumnCreate,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = board_service.create_column(
        repo, user, board_id, body.title, body.beforeColumnId, body.afterColumnId, rid
    )
    return ColumnOut(**data)


@router.patch("/{board_id}/columns/{column_id}", response_model=ColumnOut)
def patch_column(
    board_id: str,
    column_id: str,
    body: ColumnPatch,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = board_service.patch_column(
        repo, user, board_id, column_id,
        title=body.title, minimized=body.minimized, base_version=body.baseVersion, request_id=rid,
    )
    return ColumnOut(**data)


@router.delete("/{board_id}/columns/{column_id}", status_code=204)
def delete_column(
    board_id: str,
    column_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    board_service.delete_column(repo, user, board_id, column_id, rid)


@router.post("/{board_id}/columns/reorder", response_model=list[ColumnOut])
def reorder_column(
    board_id: str,
    body: ColumnReorder,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = board_service.reorder_column(
        repo, user, board_id, body.columnId, body.beforeColumnId, body.afterColumnId, rid
    )
    return [ColumnOut(**c) for c in data]


# ------- Resumos de cards (carregamento autorizado / testes) -------


@router.get("/{board_id}/cards", response_model=list[CardSummaryOut])
def list_cards(board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    from app.services import authorization as authz

    authz.require_board_editor(repo, board_id, user)
    return [CardSummaryOut(**c) for c in card_service.list_cards(repo, board_id)]
