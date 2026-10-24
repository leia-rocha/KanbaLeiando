"""Servico de cards e campos (RF17-RF23, secao 11.3).

Criacao em branco ou por modelo, salvamento do detalhe (titulo + campos +
projecao), movimentacao com fractional indexing, duplicacao independente e
exclusao definitiva. Controle separado de contentVersion e positionVersion para
que mover um card nao descarte texto que outra pessoa esta editando.
"""

from __future__ import annotations

from typing import Any

from google.cloud import firestore

from app.context import CurrentUser
from app.errors import NotFoundError, ValidationError, VersionConflictError
from app.repositories import Repo
from app.schemas.common import FieldType
from app.services import attachments as attach_service
from app.services import audit, idempotency, projection
from app.services import authorization as authz
from app.utils import sortkey
from app.utils.ids import new_id
from app.utils.text import collapse_whitespace
from app.utils.timeutils import to_iso_utc, utc_now

CREATION_ROLE = "creation"


def _ts(v) -> str:
    return to_iso_utc(v) if hasattr(v, "year") else ""


def _board_timezone(repo: Repo, board_id: str) -> str:
    snap = repo.board_ref(board_id).get()
    return (snap.to_dict() or {}).get("timezone", "America/Sao_Paulo")


def _cards_in_column(repo: Repo, board_id: str, column_id: str) -> list[dict]:
    out = []
    for doc in repo.cards_col(board_id).where("columnId", "==", column_id).stream():
        d = doc.to_dict() or {}
        d["cardId"] = doc.id
        out.append(d)
    out.sort(key=lambda c: c.get("sortKey", ""))
    return out


def _resolve_card_sortkey(cards: list[dict], before_id, after_id) -> str:
    by_id = {c["cardId"]: c for c in cards}
    before = by_id.get(before_id, {}).get("sortKey") if before_id else None
    after = by_id.get(after_id, {}).get("sortKey") if after_id else None
    if before is None and after is None and cards:
        before = cards[-1].get("sortKey")
    return sortkey.between(before, after)


def _creation_field(sort_key: str) -> dict:
    return {
        "label": "CRIACAO",
        "type": FieldType.DATETIME.value,
        "value": to_iso_utc(utc_now()),
        "sortKey": sort_key,
        "visibleOnBoard": False,
        "isDeadline": False,
        "semanticRole": CREATION_ROLE,
    }


def create_card(repo: Repo, user: CurrentUser, board_id: str, title: str,
                column_id: str, template_id: str | None, request_id: str,
                idem_key: str | None) -> dict:
    authz.require_board_editor(repo, board_id, user)
    cached = idempotency.get_cached(repo, "card_create", user.uid, idem_key)
    if cached:
        return cached

    clean_title = collapse_whitespace(title)
    if not clean_title:
        raise ValidationError("Titulo do card obrigatorio.")

    col_snap = repo.column_ref(board_id, column_id).get()
    if not col_snap.exists:
        raise NotFoundError("Coluna nao encontrada.")

    cards = _cards_in_column(repo, board_id, column_id)
    card_sort = _resolve_card_sortkey(cards, None, None)
    card_id = new_id("crd_", 20)

    fields = _fields_from_template(repo, board_id, template_id)

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        field_docs = []
        for f in fields:
            fid = new_id("fld_", 16)
            field_docs.append((fid, f))
        proj = projection.build_projection(
            [{**f, "fieldId": fid} for fid, f in field_docs]
        )
        now_tz = _board_timezone(repo, board_id)
        overdue = projection.compute_overdue(proj["dueFields"], now_tz)
        txn.set(
            repo.card_ref(board_id, card_id),
            {
                "title": clean_title,
                "columnId": column_id,
                "sortKey": card_sort,
                "contentVersion": 1,
                "positionVersion": 1,
                "visibleFieldIds": proj["visibleFieldIds"],
                "visibleFieldsSnapshot": proj["visibleFieldsSnapshot"],
                "dueFields": proj["dueFields"],
                "overdue": overdue,
                "createdByUid": user.uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        for fid, f in field_docs:
            txn.set(repo.field_ref(board_id, card_id, fid), f)
        txn.update(
            repo.column_ref(board_id, column_id),
            {"cardCount": firestore.Increment(1), "updatedAt": firestore.SERVER_TIMESTAMP},
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="card.create", entity_type="card",
            entity_id=card_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id, changed_fields={"title": clean_title, "columnId": column_id},
        )

    _txn(db.transaction())
    result = get_card_detail(repo, user, board_id, card_id)
    idempotency.store(repo, "card_create", user.uid, idem_key, result)
    return result


def _fields_from_template(repo: Repo, board_id: str, template_id: str | None) -> list[dict]:
    if not template_id:
        # Card em branco sempre recebe o campo padrao CRIACAO (RF17, DT07).
        return [_creation_field(sortkey.initial_key())]
    snap = repo.template_ref(board_id, template_id).get()
    if not snap.exists:
        raise NotFoundError("Modelo nao encontrado.")
    schema = (snap.to_dict() or {}).get("fieldSchema", [])
    fields: list[dict] = []
    for item in schema:
        ftype = item.get("type")
        is_creation = (
            item.get("semanticRole") == CREATION_ROLE
            and ftype == FieldType.DATETIME.value
        )
        fields.append(
            {
                "label": item.get("label", ""),
                "type": ftype,
                # Modelo nao guarda valores; instancia recebe vazio (DT06).
                "value": to_iso_utc(utc_now()) if is_creation else None,
                "sortKey": item.get("sortKey", sortkey.initial_key()),
                "visibleOnBoard": bool(item.get("visibleOnBoard", False)),
                "isDeadline": bool(item.get("isDeadline", False)),
                "semanticRole": item.get("semanticRole"),
            }
        )
    if not fields:
        fields = [_creation_field(sortkey.initial_key())]
    return fields


def get_card_detail(repo: Repo, user_or_visitor, board_id: str, card_id: str) -> dict:
    data = authz.assert_card_in_board(repo, board_id, card_id)
    fields = []
    for doc in repo.fields_col(board_id, card_id).stream():
        d = doc.to_dict() or {}
        d["fieldId"] = doc.id
        fields.append(d)
    fields.sort(key=lambda f: f.get("sortKey", ""))
    return {
        "cardId": card_id,
        "title": data.get("title", ""),
        "columnId": data.get("columnId", ""),
        "sortKey": data.get("sortKey", ""),
        "contentVersion": int(data.get("contentVersion", 1)),
        "positionVersion": int(data.get("positionVersion", 1)),
        "fields": [
            {
                "fieldId": f["fieldId"],
                "label": f.get("label", ""),
                "type": f.get("type"),
                "value": f.get("value"),
                "sortKey": f.get("sortKey", ""),
                "visibleOnBoard": bool(f.get("visibleOnBoard", False)),
                "isDeadline": bool(f.get("isDeadline", False)),
                "semanticRole": f.get("semanticRole"),
            }
            for f in fields
        ],
        "createdAt": _ts(data.get("createdAt")),
        "updatedAt": _ts(data.get("updatedAt")),
    }


def list_cards(repo: Repo, board_id: str) -> list[dict]:
    """Resumos para desenhar o quadro (usado em carregamento autorizado e testes)."""
    tz = _board_timezone(repo, board_id)
    now = utc_now()
    out = []
    for doc in repo.cards_col(board_id).stream():
        d = doc.to_dict() or {}
        overdue = projection.compute_overdue(d.get("dueFields", []), tz, now)
        out.append(
            {
                "cardId": doc.id,
                "title": d.get("title", ""),
                "columnId": d.get("columnId", ""),
                "sortKey": d.get("sortKey", ""),
                "contentVersion": int(d.get("contentVersion", 1)),
                "positionVersion": int(d.get("positionVersion", 1)),
                "visibleFieldsSnapshot": d.get("visibleFieldsSnapshot", []),
                "overdue": overdue,
                "createdAt": _ts(d.get("createdAt")),
                "updatedAt": _ts(d.get("updatedAt")),
            }
        )
    out.sort(key=lambda c: (c["columnId"], c["sortKey"]))
    return out


def save_card_detail(repo: Repo, user: CurrentUser, board_id: str, card_id: str,
                     title: str, fields_in: list[dict[str, Any]], content_version: int,
                     request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    clean_title = collapse_whitespace(title)
    if not clean_title:
        raise ValidationError("Titulo do card obrigatorio.")

    # Validacoes de regra antes da transacao.
    projection.validate_deadline_marks(fields_in)
    projection.validate_visible_limit(fields_in)
    _validate_field_values(fields_in)

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        card_snap = repo.card_ref(board_id, card_id).get(transaction=txn)
        if not card_snap.exists:
            raise NotFoundError("Card nao encontrado.")
        card = card_snap.to_dict() or {}
        if int(card.get("contentVersion", 1)) != content_version:
            raise VersionConflictError()

        existing = {f.id: (f.to_dict() or {}) for f in repo.fields_col(board_id, card_id).stream()}
        kept_ids: set[str] = set()
        final_fields: list[dict] = []
        n = len(fields_in)
        for index, item in enumerate(fields_in):
            fid = item.get("fieldId") or new_id("fld_", 16)
            prev = existing.get(fid, {})
            # Ordem segue a posicao na lista enviada.
            key = sortkey.between(None, None) if n == 1 else _index_key(index, n)
            semantic = prev.get("semanticRole")
            # So mantem funcao de criacao enquanto o tipo continuar DATETIME (RF22).
            if semantic == CREATION_ROLE and item["type"] != FieldType.DATETIME.value:
                semantic = None
            doc = {
                "label": collapse_whitespace(item["label"]),
                "type": item["type"],
                "value": item.get("value"),
                "sortKey": key,
                "visibleOnBoard": bool(item.get("visibleOnBoard", False)),
                "isDeadline": bool(item.get("isDeadline", False)),
                "semanticRole": semantic,
            }
            txn.set(repo.field_ref(board_id, card_id, fid), doc)
            final_fields.append({**doc, "fieldId": fid})
            kept_ids.add(fid)

        # Remove campos excluidos e programa limpeza de anexos de campos ANEXO.
        for fid in existing:
            if fid not in kept_ids:
                txn.delete(repo.field_ref(board_id, card_id, fid))

        proj = projection.build_projection(final_fields)
        tz = _board_timezone(repo, board_id)
        overdue = projection.compute_overdue(proj["dueFields"], tz)
        txn.update(
            repo.card_ref(board_id, card_id),
            {
                "title": clean_title,
                "contentVersion": int(card.get("contentVersion", 1)) + 1,
                "visibleFieldIds": proj["visibleFieldIds"],
                "visibleFieldsSnapshot": proj["visibleFieldsSnapshot"],
                "dueFields": proj["dueFields"],
                "overdue": overdue,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="card.edit", entity_type="card",
            entity_id=card_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id,
            changed_fields={"title": clean_title, "fields": len(final_fields)},
        )

    _txn(db.transaction())
    return get_card_detail(repo, user, board_id, card_id)


def _index_key(index: int, total: int) -> str:
    """Chave estavel distribuida para a posicao index de uma lista reescrita."""
    base = sortkey._BASE  # noqa: SLF001 - uso interno controlado
    # Distribui os indices uniformemente no alfabeto para manter ordem.
    pos = int((index + 1) / (total + 1) * (len(base) - 1))
    return base[max(0, min(pos, len(base) - 1))] + base[(index * 7) % len(base)]


def _validate_field_values(fields_in: list[dict[str, Any]]) -> None:
    import json

    from app.schemas.common import MAX_FIELD_VALUE_BYTES

    for item in fields_in:
        value = item.get("value")
        if value is None:
            continue
        raw = json.dumps(value, ensure_ascii=False)
        if len(raw.encode("utf-8")) > MAX_FIELD_VALUE_BYTES:
            raise PayloadError()
        if item["type"] == FieldType.LINK.value and isinstance(value, str) and value:
            low = value.strip().lower()
            if not (low.startswith("http://") or low.startswith("https://")):
                raise ValidationError("LINK deve ser um endereco http ou https.",
                                      code="invalid_link")


def PayloadError():  # noqa: N802 - fabrica de erro para manter import local
    from app.errors import PayloadTooLargeError

    return PayloadTooLargeError("Valor de campo acima do limite de 100 KiB.")


def move_card(repo: Repo, user: CurrentUser, board_id: str, card_id: str,
              target_column_id: str, before_id, after_id, position_version: int,
              request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    db = repo.db

    @firestore.transactional
    def _txn(txn):
        snap = repo.card_ref(board_id, card_id).get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Card nao encontrado.")
        card = snap.to_dict() or {}
        if int(card.get("positionVersion", 1)) != position_version:
            raise VersionConflictError()
        target_col = repo.column_ref(board_id, target_column_id).get(transaction=txn)
        if not target_col.exists:
            raise NotFoundError("Coluna de destino nao encontrada.")
        old_col = card.get("columnId")

        # Revalida vizinhos pelos IDs reais (RF31, secao 11.3).
        siblings = _cards_in_column(repo, board_id, target_column_id)
        siblings = [c for c in siblings if c["cardId"] != card_id]
        new_key = _resolve_card_sortkey(siblings, before_id, after_id)

        txn.update(
            repo.card_ref(board_id, card_id),
            {
                "columnId": target_column_id,
                "sortKey": new_key,
                "positionVersion": int(card.get("positionVersion", 1)) + 1,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        if old_col and old_col != target_column_id:
            txn.update(repo.column_ref(board_id, old_col),
                       {"cardCount": firestore.Increment(-1)})
            txn.update(repo.column_ref(board_id, target_column_id),
                       {"cardCount": firestore.Increment(1)})
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="card.move", entity_type="card",
            entity_id=card_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id,
            changed_fields={"from": old_col, "to": target_column_id},
        )

    _txn(db.transaction())
    return get_card_detail(repo, user, board_id, card_id)


def duplicate_card(repo: Repo, user: CurrentUser, board_id: str, card_id: str,
                   request_id: str, idem_key: str | None) -> dict:
    authz.require_board_editor(repo, board_id, user)
    cached = idempotency.get_cached(repo, "card_duplicate", user.uid, idem_key)
    if cached:
        return cached

    src = authz.assert_card_in_board(repo, board_id, card_id)
    src_fields = []
    for doc in repo.fields_col(board_id, card_id).stream():
        d = doc.to_dict() or {}
        d["fieldId"] = doc.id
        src_fields.append(d)
    src_attachments = []
    for doc in repo.attachments_col(board_id, card_id).stream():
        d = doc.to_dict() or {}
        d["attachmentId"] = doc.id
        src_attachments.append(d)

    new_card_id = new_id("crd_", 20)
    # Copia de arquivos acontece fora da transacao (efeito externo, secao 11.3).
    field_id_map: dict[str, str] = {}
    new_fields = []
    for f in sorted(src_fields, key=lambda x: x.get("sortKey", "")):
        nfid = new_id("fld_", 16)
        field_id_map[f["fieldId"]] = nfid
        value = f.get("value")
        semantic = f.get("semanticRole")
        if semantic == CREATION_ROLE and f.get("type") == FieldType.DATETIME.value:
            value = to_iso_utc(utc_now())  # reinicia CRIACAO (DT09)
        new_fields.append({
            "fieldId": nfid,
            "label": f.get("label", ""),
            "type": f.get("type"),
            "value": value,
            "sortKey": f.get("sortKey", sortkey.initial_key()),
            "visibleOnBoard": bool(f.get("visibleOnBoard", False)),
            "isDeadline": bool(f.get("isDeadline", False)),
            "semanticRole": semantic,
        })

    new_attachments = attach_service.copy_attachments_for_duplicate(
        repo, board_id, card_id, new_card_id, src_attachments, field_id_map
    )

    cards = _cards_in_column(repo, board_id, src.get("columnId"))
    # Posiciona logo apos o original (DT09).
    after_original = None
    src_key = src.get("sortKey")
    for i, c in enumerate(cards):
        if c["cardId"] == card_id and i + 1 < len(cards):
            after_original = cards[i + 1]["cardId"]
    new_key = _resolve_card_sortkey(
        cards, card_id, after_original
    ) if src_key else sortkey.between(src_key, None)

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        proj_fields = [{**f} for f in new_fields]
        for f in proj_fields:
            fid = f["fieldId"]
            f["attachmentsSnapshot"] = [
                {"attachmentId": a["attachmentId"], "originalName": a["originalName"]}
                for a in new_attachments if a.get("fieldId") == fid
            ]
        proj = projection.build_projection(proj_fields)
        tz = _board_timezone(repo, board_id)
        overdue = projection.compute_overdue(proj["dueFields"], tz)
        txn.set(
            repo.card_ref(board_id, new_card_id),
            {
                "title": collapse_whitespace(src.get("title", "")) + " copia",
                "columnId": src.get("columnId"),
                "sortKey": new_key,
                "contentVersion": 1,
                "positionVersion": 1,
                "visibleFieldIds": proj["visibleFieldIds"],
                "visibleFieldsSnapshot": proj["visibleFieldsSnapshot"],
                "dueFields": proj["dueFields"],
                "overdue": overdue,
                "createdByUid": user.uid,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        for f in new_fields:
            fid = f.pop("fieldId")
            txn.set(repo.field_ref(board_id, new_card_id, fid), f)
            f["fieldId"] = fid
        for a in new_attachments:
            aid = a["attachmentId"]
            txn.set(repo.attachment_ref(board_id, new_card_id, aid),
                    {k: v for k, v in a.items() if k != "attachmentId"})
        txn.update(repo.column_ref(board_id, src.get("columnId")),
                   {"cardCount": firestore.Increment(1)})
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="card.duplicate", entity_type="card",
            entity_id=new_card_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id, changed_fields={"source": card_id},
        )

    _txn(db.transaction())
    result = get_card_detail(repo, user, board_id, new_card_id)
    idempotency.store(repo, "card_duplicate", user.uid, idem_key, result)
    return result


def delete_card(repo: Repo, user: CurrentUser, board_id: str, card_id: str,
                request_id: str) -> None:
    authz.require_board_editor(repo, board_id, user)
    snap = repo.card_ref(board_id, card_id).get()
    if not snap.exists:
        return  # idempotente (RF23)
    card = snap.to_dict() or {}
    title = card.get("title", "")
    column_id = card.get("columnId")

    # Programa remocao de objetos do bucket (efeito externo, fora de transacao).
    attach_service.schedule_card_attachments_cleanup(repo, board_id, card_id)

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        for f in repo.fields_col(board_id, card_id).stream():
            txn.delete(f.reference)
        for a in repo.attachments_col(board_id, card_id).stream():
            txn.delete(a.reference)
        txn.delete(repo.card_ref(board_id, card_id))
        if column_id:
            txn.update(repo.column_ref(board_id, column_id),
                       {"cardCount": firestore.Increment(-1)})
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="card.delete", entity_type="card",
            entity_id=card_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id, changed_fields={"title": title},
        )

    _txn(db.transaction())
