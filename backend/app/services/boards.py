"""Servico de kanbans (RF12, RF13, RF14, RF36).

Criacao atomica (dono + coluna INICIO), renomeacao, listagem e exclusao com
operacao duravel de limpeza. Colunas e sua reorganizacao/minimizacao.
"""

from __future__ import annotations

from google.cloud import firestore

from app.context import CurrentUser
from app.errors import ConflictError, NotFoundError, ValidationError, VersionConflictError
from app.repositories import Repo
from app.schemas.common import MemberRole
from app.services import audit, idempotency
from app.services import authorization as authz
from app.utils import sortkey
from app.utils.ids import new_id
from app.utils.text import collapse_whitespace
from app.utils.timeutils import to_iso_utc


def _ts(value) -> str:
    return to_iso_utc(value) if hasattr(value, "year") else ""


# ------------------------------- Boards -------------------------------


def create_board(repo: Repo, user: CurrentUser, name: str, request_id: str,
                 idem_key: str | None) -> dict:
    cached = idempotency.get_cached(repo, "board_create", user.uid, idem_key)
    if cached:
        return cached

    title = collapse_whitespace(name)
    if not title:
        raise ValidationError("Nome do kanban obrigatorio.")

    board_id = new_id("brd_", 20)
    column_id = new_id("col_", 20)
    db = repo.db

    @firestore.transactional
    def _txn(txn):
        txn.set(
            repo.board_ref(board_id),
            {
                "title": title,
                "timezone": "America/Sao_Paulo",
                "version": 1,
                "columnsOrderVersion": 1,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        txn.set(
            repo.column_ref(board_id, column_id),
            {
                "title": "INICIO",
                "sortKey": sortkey.initial_key(),
                "minimized": False,
                "cardCount": 0,
                "version": 1,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        txn.set(
            repo.board_security_ref(board_id),
            {
                "ownerUid": user.uid,
                "status": "active",
                "publicEnabled": False,
                "publicShareVersion": 0,
                "version": 1,
            },
        )
        txn.set(
            repo.member_ref(board_id, user.uid),
            {
                "role": MemberRole.OWNER.value,
                "grantedAt": firestore.SERVER_TIMESTAMP,
                "grantedByUid": user.uid,
            },
        )
        txn.set(
            repo.board_ref_doc(user.uid, board_id),
            {
                "boardId": board_id,
                "title": title,
                "role": MemberRole.OWNER.value,
                "grantedAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="board.create",
            entity_type="board", entity_id=board_id, actor_uid=user.uid,
            actor_name=user.name, request_id=request_id,
            changed_fields={"title": title},
        )

    _txn(db.transaction())
    result = get_board(repo, user, board_id)
    idempotency.store(repo, "board_create", user.uid, idem_key, result)
    return result


def list_boards(repo: Repo, user: CurrentUser) -> dict:
    docs = repo.board_refs_col(user.uid).stream()
    boards = []
    for doc in docs:
        data = doc.to_dict() or {}
        boards.append(
            {
                "boardId": data.get("boardId", doc.id),
                "title": data.get("title", ""),
                "role": data.get("role", MemberRole.EDITOR.value),
                "grantedAt": _ts(data.get("grantedAt")),
            }
        )
    boards.sort(key=lambda b: b["title"].casefold())
    return {"boards": boards}


def get_board(repo: Repo, user: CurrentUser, board_id: str) -> dict:
    role = authz.require_board_editor(repo, board_id, user)
    snap = repo.board_ref(board_id).get()
    if not snap.exists:
        raise NotFoundError("Kanban nao encontrado.")
    data = snap.to_dict() or {}
    return {
        "boardId": board_id,
        "title": data.get("title", ""),
        "timezone": data.get("timezone", "America/Sao_Paulo"),
        "version": int(data.get("version", 1)),
        "columnsOrderVersion": int(data.get("columnsOrderVersion", 1)),
        "role": role.value,
        "createdAt": _ts(data.get("createdAt")),
        "updatedAt": _ts(data.get("updatedAt")),
    }


def rename_board(repo: Repo, user: CurrentUser, board_id: str, name: str,
                 base_version: int, request_id: str) -> dict:
    authz.require_board_owner(repo, board_id, user)
    title = collapse_whitespace(name)
    if not title:
        raise ValidationError("Nome do kanban obrigatorio.")
    db = repo.db

    @firestore.transactional
    def _txn(txn):
        snap = repo.board_ref(board_id).get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Kanban nao encontrado.")
        data = snap.to_dict() or {}
        if int(data.get("version", 1)) != base_version:
            raise VersionConflictError()
        txn.update(
            repo.board_ref(board_id),
            {
                "title": title,
                "version": int(data.get("version", 1)) + 1,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="board.rename", entity_type="board",
            entity_id=board_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id,
            changed_fields={"title": {"old": data.get("title"), "new": title}},
        )

    _txn(db.transaction())
    # Atualiza projecoes de navegacao dos membros.
    _sync_board_ref_titles(repo, board_id, title)
    return get_board(repo, user, board_id)


def _sync_board_ref_titles(repo: Repo, board_id: str, title: str) -> None:
    members = repo.members_col(board_id).stream()
    for m in members:
        ref = repo.board_ref_doc(m.id, board_id)
        if ref.get().exists:
            ref.update({"title": title, "updatedAt": firestore.SERVER_TIMESTAMP})


# ------------------------------- Columns -------------------------------


def _columns_sorted(repo: Repo, board_id: str) -> list[dict]:
    cols = []
    for doc in repo.columns_col(board_id).stream():
        d = doc.to_dict() or {}
        d["columnId"] = doc.id
        cols.append(d)
    cols.sort(key=lambda c: c.get("sortKey", ""))
    return cols


def list_columns(repo: Repo, user: CurrentUser, board_id: str) -> list[dict]:
    authz.require_board_editor(repo, board_id, user)
    return [
        {
            "columnId": c["columnId"],
            "title": c.get("title", ""),
            "sortKey": c.get("sortKey", ""),
            "minimized": bool(c.get("minimized", False)),
            "cardCount": int(c.get("cardCount", 0)),
            "version": int(c.get("version", 1)),
        }
        for c in _columns_sorted(repo, board_id)
    ]


def create_column(repo: Repo, user: CurrentUser, board_id: str, title: str,
                  before_id: str | None, after_id: str | None, request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    name = collapse_whitespace(title)
    if not name:
        raise ValidationError("Nome da coluna obrigatorio.")
    cols = _columns_sorted(repo, board_id)
    key = _resolve_sortkey(cols, before_id, after_id)
    column_id = new_id("col_", 20)

    repo.column_ref(board_id, column_id).set(
        {
            "title": name,
            "sortKey": key,
            "minimized": False,
            "cardCount": 0,
            "version": 1,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    audit.record_now(
        repo, board_id=board_id, action="column.create", entity_type="column",
        entity_id=column_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id, changed_fields={"title": name},
    )
    return {
        "columnId": column_id, "title": name, "sortKey": key,
        "minimized": False, "cardCount": 0, "version": 1,
    }


def _resolve_sortkey(cols: list[dict], before_id: str | None, after_id: str | None) -> str:
    by_id = {c["columnId"]: c for c in cols}
    before_key = by_id.get(before_id, {}).get("sortKey") if before_id else None
    after_key = by_id.get(after_id, {}).get("sortKey") if after_id else None
    if before_key is None and after_key is None and cols:
        before_key = cols[-1].get("sortKey")
    return sortkey.between(before_key, after_key)


def patch_column(repo: Repo, user: CurrentUser, board_id: str, column_id: str, *,
                 title, minimized, base_version: int, request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    db = repo.db

    @firestore.transactional
    def _txn(txn):
        snap = repo.column_ref(board_id, column_id).get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Coluna nao encontrada.")
        data = snap.to_dict() or {}
        if int(data.get("version", 1)) != base_version:
            raise VersionConflictError()
        updates: dict = {
            "version": int(data.get("version", 1)) + 1,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        changed: dict = {}
        action = "column.update"
        if title is not None:
            name = collapse_whitespace(title)
            if not name:
                raise ValidationError("Nome da coluna obrigatorio.")
            updates["title"] = name
            changed["title"] = {"old": data.get("title"), "new": name}
            action = "column.rename"
        if minimized is not None:
            updates["minimized"] = bool(minimized)
            changed["minimized"] = bool(minimized)
            action = "column.minimize" if minimized else "column.expand"
        txn.update(repo.column_ref(board_id, column_id), updates)
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action=action, entity_type="column",
            entity_id=column_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id, changed_fields=changed,
        )

    _txn(db.transaction())
    snap = repo.column_ref(board_id, column_id).get()
    d = snap.to_dict() or {}
    return {
        "columnId": column_id, "title": d.get("title", ""), "sortKey": d.get("sortKey", ""),
        "minimized": bool(d.get("minimized")), "cardCount": int(d.get("cardCount", 0)),
        "version": int(d.get("version", 1)),
    }


def reorder_column(repo: Repo, user: CurrentUser, board_id: str, column_id: str,
                   before_id: str | None, after_id: str | None, request_id: str) -> list[dict]:
    authz.require_board_editor(repo, board_id, user)
    cols = _columns_sorted(repo, board_id)
    if column_id not in {c["columnId"] for c in cols}:
        raise NotFoundError("Coluna nao encontrada.")
    others = [c for c in cols if c["columnId"] != column_id]
    key = _resolve_sortkey(others, before_id, after_id)
    repo.column_ref(board_id, column_id).update(
        {"sortKey": key, "updatedAt": firestore.SERVER_TIMESTAMP}
    )
    repo.board_ref(board_id).update(
        {"columnsOrderVersion": firestore.Increment(1), "updatedAt": firestore.SERVER_TIMESTAMP}
    )
    audit.record_now(
        repo, board_id=board_id, action="column.reorder", entity_type="column",
        entity_id=column_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id, changed_fields={"sortKey": key},
    )
    return list_columns(repo, user, board_id)


def delete_column(repo: Repo, user: CurrentUser, board_id: str, column_id: str,
                  request_id: str) -> None:
    authz.require_board_editor(repo, board_id, user)
    db = repo.db

    @firestore.transactional
    def _txn(txn):
        col_snap = repo.column_ref(board_id, column_id).get(transaction=txn)
        if not col_snap.exists:
            raise NotFoundError("Coluna nao encontrada.")
        # Revalida vazio na transacao: contador do cliente nao e prova (RF14).
        count = int((col_snap.to_dict() or {}).get("cardCount", 0))
        if count > 0:
            raise ConflictError("Nao e possivel excluir coluna com cards.",
                                code="column_not_empty")
        # Preserva ao menos uma coluna (DT16): nao exclui a ultima.
        all_cols = list(repo.columns_col(board_id).stream())
        if len(all_cols) <= 1:
            raise ConflictError("O kanban deve ter ao menos uma coluna.",
                                code="last_column")
        # Recontagem defensiva de cards diretamente na transacao.
        cards_in_col = (
            repo.cards_col(board_id).where("columnId", "==", column_id).limit(1).get()
        )
        if len(cards_in_col) > 0:
            raise ConflictError("Nao e possivel excluir coluna com cards.",
                                code="column_not_empty")
        txn.delete(repo.column_ref(board_id, column_id))
        txn.update(
            repo.board_ref(board_id),
            {"columnsOrderVersion": firestore.Increment(1),
             "updatedAt": firestore.SERVER_TIMESTAMP},
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="column.delete", entity_type="column",
            entity_id=column_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id,
        )

    _txn(db.transaction())
