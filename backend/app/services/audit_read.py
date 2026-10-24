"""Leitura paginada da auditoria do quadro (RF34, secao 14.2)."""

from __future__ import annotations

from app.context import CurrentUser
from app.repositories import Repo
from app.services import authorization as authz
from app.utils.timeutils import to_iso_utc


def list_events(repo: Repo, user: CurrentUser, board_id: str, cursor: str | None,
                limit: int) -> dict:
    authz.require_board_editor(repo, board_id, user)
    limit = max(1, min(limit, 100))
    from google.cloud import firestore

    query = (
        repo.audit_col(board_id)
        .order_by("occurredAt", direction=firestore.Query.DESCENDING)
        .limit(limit + 1)
    )
    if cursor:
        cur_snap = repo.audit_ref(board_id, cursor).get()
        if cur_snap.exists:
            query = query.start_after(cur_snap)
    docs = list(query.stream())
    events = []
    for doc in docs[:limit]:
        d = doc.to_dict() or {}
        occurred = d.get("occurredAt")
        events.append(
            {
                "eventId": doc.id,
                "action": d.get("action", ""),
                "entityType": d.get("entityType", ""),
                "entityId": d.get("entityId", ""),
                "actorUid": d.get("actorUid", ""),
                "actorNameSnapshot": d.get("actorNameSnapshot", ""),
                "occurredAt": to_iso_utc(occurred) if hasattr(occurred, "year") else "",
                "requestId": d.get("requestId", ""),
                "changedFields": d.get("changedFields"),
            }
        )
    next_cursor = docs[limit - 1].id if len(docs) > limit else None
    return {"events": events, "nextCursor": next_cursor}
