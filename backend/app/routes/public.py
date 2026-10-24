"""Acesso publico em tempo real (RF33, secao 10.3).

POST /public/session valida boardId+token e emite credencial temporaria. As
rotas de leitura publica devolvem o mesmo conteudo do quadro, nunca auditoria,
modelos, membros ou outros quadros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_public_visitor, get_repo
from app.repositories import Repo
from app.schemas.board import BoardOut, CardSummaryOut, ColumnOut
from app.schemas.sharing import PublicSessionRequest, PublicSessionResponse
from app.services import cards as card_service
from app.services import sharing as sharing_service
from app.utils.timeutils import to_iso_utc

router = APIRouter()


@router.post("/public/session", response_model=PublicSessionResponse)
def public_session(body: PublicSessionRequest, repo: Repo = Depends(get_repo)):
    data = sharing_service.open_public_session(repo, body.boardId, body.token)
    return PublicSessionResponse(**data)


def _ts(v) -> str:
    return to_iso_utc(v) if hasattr(v, "year") else ""


@router.get("/public/boards/{board_id}", response_model=BoardOut)
def public_board(
    board_id: str, visitor=Depends(get_public_visitor), repo: Repo = Depends(get_repo)
):
    if visitor.board_id != board_id:
        from app.errors import ForbiddenError

        raise ForbiddenError("Credencial nao corresponde a este quadro.")
    snap = repo.board_ref(board_id).get()
    if not snap.exists:
        from app.errors import NotFoundError

        raise NotFoundError("Quadro indisponivel.")
    d = snap.to_dict() or {}
    return BoardOut(
        boardId=board_id,
        title=d.get("title", ""),
        timezone=d.get("timezone", "America/Sao_Paulo"),
        version=int(d.get("version", 1)),
        columnsOrderVersion=int(d.get("columnsOrderVersion", 1)),
        role="editor",  # apenas para o schema; a UI publica e somente leitura
        createdAt=_ts(d.get("createdAt")),
        updatedAt=_ts(d.get("updatedAt")),
    )


@router.get("/public/boards/{board_id}/columns", response_model=list[ColumnOut])
def public_columns(
    board_id: str, visitor=Depends(get_public_visitor), repo: Repo = Depends(get_repo)
):
    if visitor.board_id != board_id:
        from app.errors import ForbiddenError

        raise ForbiddenError("Credencial nao corresponde a este quadro.")
    cols = []
    for doc in repo.columns_col(board_id).stream():
        d = doc.to_dict() or {}
        cols.append(
            ColumnOut(
                columnId=doc.id,
                title=d.get("title", ""),
                sortKey=d.get("sortKey", ""),
                minimized=bool(d.get("minimized", False)),
                cardCount=int(d.get("cardCount", 0)),
                version=int(d.get("version", 1)),
            )
        )
    cols.sort(key=lambda c: c.sortKey)
    return cols


@router.get("/public/boards/{board_id}/cards", response_model=list[CardSummaryOut])
def public_cards(
    board_id: str, visitor=Depends(get_public_visitor), repo: Repo = Depends(get_repo)
):
    if visitor.board_id != board_id:
        from app.errors import ForbiddenError

        raise ForbiddenError("Credencial nao corresponde a este quadro.")
    return [CardSummaryOut(**c) for c in card_service.list_cards(repo, board_id)]
