"""Registro de auditoria de dominio (secao 11.1).

Eventos imutaveis gravados na mesma transacao da mudanca quando couber. Nunca
guarda binarios, senhas, tokens ou URLs assinadas. Resumos de diferencas sao
limitados em tamanho.
"""

from __future__ import annotations

import json
from typing import Any

from app.repositories import Repo
from app.utils.ids import new_id

_MAX_SUMMARY_BYTES = 8 * 1024


def _truncate(changed: dict[str, Any] | None) -> dict[str, Any] | None:
    if not changed:
        return changed
    raw = json.dumps(changed, ensure_ascii=False)
    if len(raw.encode("utf-8")) <= _MAX_SUMMARY_BYTES:
        return changed
    return {"_truncated": True, "note": "Resumo de alteracoes muito grande para auditoria."}


def build_event(
    *,
    board_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_uid: str,
    actor_name: str,
    request_id: str,
    changed_fields: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Monta (event_id, payload) para gravar em transacao."""
    event_id = new_id("evt_", 20)
    from google.cloud import firestore

    payload = {
        "eventId": event_id,
        "boardId": board_id,
        "action": action,
        "entityType": entity_type,
        "entityId": entity_id,
        "actorUid": actor_uid,
        "actorNameSnapshot": actor_name,
        "occurredAt": firestore.SERVER_TIMESTAMP,
        "requestId": request_id,
        "changedFields": _truncate(changed_fields),
    }
    return event_id, payload


def record_in_transaction(
    repo: Repo,
    txn,
    *,
    board_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_uid: str,
    actor_name: str,
    request_id: str,
    changed_fields: dict[str, Any] | None = None,
) -> str:
    event_id, payload = build_event(
        board_id=board_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_uid=actor_uid,
        actor_name=actor_name,
        request_id=request_id,
        changed_fields=changed_fields,
    )
    txn.set(repo.audit_ref(board_id, event_id), payload)
    return event_id


def record_now(
    repo: Repo,
    *,
    board_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_uid: str,
    actor_name: str,
    request_id: str,
    changed_fields: dict[str, Any] | None = None,
) -> str:
    """Grava um evento fora de transacao (operacoes em multiplas etapas)."""
    event_id, payload = build_event(
        board_id=board_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_uid=actor_uid,
        actor_name=actor_name,
        request_id=request_id,
        changed_fields=changed_fields,
    )
    repo.audit_ref(board_id, event_id).set(payload)
    return event_id
