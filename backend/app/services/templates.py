"""Modelos reutilizaveis do kanban (RF24-RF26, DT06, DT10).

Um modelo guarda apenas a estrutura de campos (ordem, tipos, visibilidade, marca
de prazo, semanticRole). Nao guarda valores, anexos, titulo ou itens de
checklist. Nomes unicos no mesmo kanban apos normalizacao.
"""

from __future__ import annotations

from google.cloud import firestore

from app.context import CurrentUser
from app.errors import ConflictError, NotFoundError, ValidationError, VersionConflictError
from app.repositories import Repo
from app.services import audit
from app.services import authorization as authz
from app.utils.ids import new_id
from app.utils.text import collapse_whitespace, normalize_name
from app.utils.timeutils import to_iso_utc


def _ts(v) -> str:
    return to_iso_utc(v) if hasattr(v, "year") else ""


def _schema_from_card(repo: Repo, board_id: str, card_id: str) -> list[dict]:
    fields = []
    for doc in repo.fields_col(board_id, card_id).stream():
        d = doc.to_dict() or {}
        fields.append(
            {
                "label": d.get("label", ""),
                "type": d.get("type"),
                "sortKey": d.get("sortKey", ""),
                "visibleOnBoard": bool(d.get("visibleOnBoard", False)),
                "isDeadline": bool(d.get("isDeadline", False)),
                "semanticRole": d.get("semanticRole"),
            }
        )
    fields.sort(key=lambda f: f.get("sortKey", ""))
    return fields


def create_template(repo: Repo, user: CurrentUser, board_id: str, name: str,
                    from_card_id: str, replace_existing: bool, request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    clean = collapse_whitespace(name)
    if not clean:
        raise ValidationError("Nome do modelo obrigatorio.")
    norm = normalize_name(clean)

    authz.assert_card_in_board(repo, board_id, from_card_id)
    schema = _schema_from_card(repo, board_id, from_card_id)

    existing = list(
        repo.templates_col(board_id).where("normalizedName", "==", norm).limit(1).stream()
    )
    if existing and not replace_existing:
        raise ConflictError("Ja existe um modelo com este nome.", code="template_name_exists")

    if existing and replace_existing:
        tpl_ref = existing[0].reference
        template_id = existing[0].id
        version = int((existing[0].to_dict() or {}).get("version", 1)) + 1
    else:
        template_id = new_id("tpl_", 20)
        tpl_ref = repo.template_ref(board_id, template_id)
        version = 1

    tpl_ref.set(
        {
            "name": clean,
            "normalizedName": norm,
            "fieldSchema": schema,
            "createdByUid": user.uid,
            "version": version,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    audit.record_now(
        repo, board_id=board_id, action="template.create", entity_type="template",
        entity_id=template_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id, changed_fields={"name": clean},
    )
    snap = tpl_ref.get()
    return _out(template_id, snap.to_dict() or {})


def list_templates(repo: Repo, user: CurrentUser, board_id: str) -> list[dict]:
    authz.require_board_editor(repo, board_id, user)
    out = []
    for doc in repo.templates_col(board_id).stream():
        out.append(_out(doc.id, doc.to_dict() or {}))
    out.sort(key=lambda t: t["name"].casefold())
    return out


def rename_template(repo: Repo, user: CurrentUser, board_id: str, template_id: str,
                    name: str, base_version: int, request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    clean = collapse_whitespace(name)
    if not clean:
        raise ValidationError("Nome do modelo obrigatorio.")
    norm = normalize_name(clean)

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        snap = repo.template_ref(board_id, template_id).get(transaction=txn)
        if not snap.exists:
            raise NotFoundError("Modelo nao encontrado.")
        data = snap.to_dict() or {}
        if int(data.get("version", 1)) != base_version:
            raise VersionConflictError()
        dup = list(
            repo.templates_col(board_id).where("normalizedName", "==", norm).limit(2).stream()
        )
        if any(d.id != template_id for d in dup):
            raise ConflictError("Ja existe um modelo com este nome.",
                                code="template_name_exists")
        txn.update(
            repo.template_ref(board_id, template_id),
            {
                "name": clean,
                "normalizedName": norm,
                "version": int(data.get("version", 1)) + 1,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        audit.record_in_transaction(
            repo, txn, board_id=board_id, action="template.rename", entity_type="template",
            entity_id=template_id, actor_uid=user.uid, actor_name=user.name,
            request_id=request_id, changed_fields={"name": clean},
        )

    _txn(db.transaction())
    snap = repo.template_ref(board_id, template_id).get()
    return _out(template_id, snap.to_dict() or {})


def delete_template(repo: Repo, user: CurrentUser, board_id: str, template_id: str,
                    request_id: str) -> None:
    authz.require_board_editor(repo, board_id, user)
    snap = repo.template_ref(board_id, template_id).get()
    if not snap.exists:
        return
    repo.template_ref(board_id, template_id).delete()
    audit.record_now(
        repo, board_id=board_id, action="template.delete", entity_type="template",
        entity_id=template_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id,
    )


def _out(template_id: str, data: dict) -> dict:
    return {
        "templateId": template_id,
        "name": data.get("name", ""),
        "createdByUid": data.get("createdByUid", ""),
        "version": int(data.get("version", 1)),
        "createdAt": _ts(data.get("createdAt")),
        "updatedAt": _ts(data.get("updatedAt")),
    }
