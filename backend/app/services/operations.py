"""Operacoes duraveis: exclusao de board em lotes, limpeza de anexos e exclusao
de usuario com transferencia de propriedade (secao 12, RF36, RF37).

Usa cursores e lotes idempotentes, suportando interrupcao e repeticao sem
depender da memoria do container. Tarefas de Cloud Tasks so recebem 2xx apos a
etapa persistente concluir.
"""

from __future__ import annotations

from google.cloud import firestore

from app.repositories import Repo
from app.schemas.common import MemberRole, UserStatus
from app.services import tasks as tasks_service
from app.utils.ids import new_id

_BATCH = 200


def start_board_deletion(repo: Repo, board_id: str, actor_uid: str) -> str:
    """Retira acesso imediato e cria operacao duravel de limpeza fisica."""
    ref = repo.board_security_ref(board_id)
    ref.update({"status": "deleting", "publicEnabled": False})
    # Remove referencias da tela inicial dos membros.
    for m in repo.members_col(board_id).stream():
        repo.board_ref_doc(m.id, board_id).delete()

    op_id = new_id("op_", 20)
    repo.operation_ref(op_id).set(
        {
            "kind": "board_delete",
            "status": "pending",
            "boardId": board_id,
            "actorUid": actor_uid,
            "cursor": None,
            "retryCount": 0,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    tasks_service.enqueue(op_id, "board_delete")
    return op_id


def run_operation(repo: Repo, operation_id: str) -> dict:
    """Executa/continua uma operacao. Idempotente; pode ser chamada repetidas vezes."""
    snap = repo.operation_ref(operation_id).get()
    if not snap.exists:
        return {"status": "not_found"}
    data = snap.to_dict() or {}
    kind = data.get("kind")
    if data.get("status") == "completed":
        return {"status": "completed"}

    if kind == "board_delete":
        return _run_board_delete(repo, operation_id, data)
    if kind == "attachments_cleanup":
        return _run_attachments_cleanup(repo, operation_id, data)
    if kind == "user_delete":
        return _run_user_delete(repo, operation_id, data)
    repo.operation_ref(operation_id).update({"status": "failed",
                                             "lastErrorCode": "unknown_kind"})
    return {"status": "failed"}


def _run_board_delete(repo: Repo, op_id: str, data: dict) -> dict:
    board_id = data["boardId"]
    repo.operation_ref(op_id).update({"status": "running",
                                      "updatedAt": firestore.SERVER_TIMESTAMP})
    # Exclui cards (e subcolecoes fields/attachments) em lotes.
    while True:
        cards = list(repo.cards_col(board_id).limit(_BATCH).stream())
        if not cards:
            break
        for card in cards:
            for f in repo.fields_col(board_id, card.id).stream():
                f.reference.delete()
            for a in repo.attachments_col(board_id, card.id).stream():
                _delete_object((a.to_dict() or {}).get("objectKey"))
                a.reference.delete()
            card.reference.delete()
    # Colunas, modelos, auditoria, membros, seguranca.
    for col in repo.columns_col(board_id).stream():
        col.reference.delete()
    for tpl in repo.templates_col(board_id).stream():
        tpl.reference.delete()
    while True:
        events = list(repo.audit_col(board_id).limit(_BATCH).stream())
        if not events:
            break
        for e in events:
            e.reference.delete()
    for m in repo.members_col(board_id).stream():
        m.reference.delete()
    repo.board_security_ref(board_id).delete()
    repo.board_ref(board_id).delete()
    repo.operation_ref(op_id).update({"status": "completed",
                                      "updatedAt": firestore.SERVER_TIMESTAMP})
    return {"status": "completed"}


def _run_attachments_cleanup(repo: Repo, op_id: str, data: dict) -> dict:
    keys = data.get("targetIds", [])
    cursor = int(data.get("cursor", 0))
    repo.operation_ref(op_id).update({"status": "running"})
    while cursor < len(keys):
        _delete_object(keys[cursor])
        cursor += 1
        if cursor % 50 == 0:
            repo.operation_ref(op_id).update({"cursor": cursor})
    repo.operation_ref(op_id).update({"status": "completed", "cursor": cursor})
    return {"status": "completed"}


def _delete_object(object_key: str | None) -> None:
    if not object_key:
        return
    try:
        from app.clients import get_bucket

        blob = get_bucket().get_blob(object_key)
        if blob is not None:
            blob.delete()
    except Exception:  # noqa: BLE001
        pass


# ------------------------- Exclusao de usuario (RF37) -------------------------


def start_user_deletion(repo: Repo, target_uid: str, actor_uid: str) -> str:
    """Marca o perfil como deleting, revoga sessoes e cria operacao duravel."""
    from app.clients import get_auth_client

    repo.user_ref(target_uid).update({"status": UserStatus.DELETING.value})
    try:
        auth = get_auth_client()
        auth.update_user(target_uid, disabled=True)
        auth.revoke_refresh_tokens(target_uid)
    except Exception:  # noqa: BLE001
        pass

    op_id = new_id("op_", 20)
    repo.operation_ref(op_id).set(
        {
            "kind": "user_delete",
            "status": "pending",
            "targetUid": target_uid,
            "actorUid": actor_uid,
            "retryCount": 0,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    enqueued = tasks_service.enqueue(op_id, "user_delete")
    if not enqueued:
        # Sem fila: executa inline para nao deixar conta em estado intermediario.
        run_operation(repo, op_id)
    return op_id


def _run_user_delete(repo: Repo, op_id: str, data: dict) -> dict:
    target_uid = data["targetUid"]
    repo.operation_ref(op_id).update({"status": "running"})

    # Analisa cada board de que o usuario e dono.
    # Percorre boardSecurity por ownerUid (collection_group pode faltar indice em dev).
    for sec_doc in repo.db.collection("boardSecurity").where(
        "ownerUid", "==", target_uid
    ).stream():
        board_id = sec_doc.id
        _process_owned_board(repo, board_id, target_uid)

    # Remove vinculos do usuario em boards de terceiros (apenas editor).
    for sec_doc in repo.db.collection("boardSecurity").stream():
        board_id = sec_doc.id
        member = repo.member_ref(board_id, target_uid).get()
        if member.exists and (sec_doc.to_dict() or {}).get("ownerUid") != target_uid:
            repo.member_ref(board_id, target_uid).delete()
            repo.board_ref_doc(target_uid, board_id).delete()

    # Conclui limpeza do perfil e exclusao no Firebase Auth.
    for ref_doc in repo.board_refs_col(target_uid).stream():
        ref_doc.reference.delete()
    repo.user_ref(target_uid).delete()
    try:
        from app.clients import get_auth_client

        get_auth_client().delete_user(target_uid)
    except Exception:  # noqa: BLE001
        pass

    repo.operation_ref(op_id).update({"status": "completed",
                                      "updatedAt": firestore.SERVER_TIMESTAMP})
    return {"status": "completed"}


def _process_owned_board(repo: Repo, board_id: str, owner_uid: str) -> None:
    """Se o dono for o unico editor, exclui o board. Senao, transfere para o
    editor com grantedAt mais antigo (desempate por UID)."""
    members = []
    for doc in repo.members_col(board_id).stream():
        d = doc.to_dict() or {}
        if doc.id == owner_uid:
            continue
        # Ignora identidades tecnicas de leitor publico e membros em exclusao.
        if doc.id.startswith("public_"):
            continue
        profile = repo.user_ref(doc.id).get().to_dict() or {}
        if profile.get("status") == UserStatus.DELETING.value:
            continue
        members.append((doc.id, d.get("grantedAt")))

    if not members:
        start_board_deletion(repo, board_id, owner_uid)
        return

    def _sort_key(item):
        uid, granted = item
        ts = granted.timestamp() if hasattr(granted, "timestamp") else 0
        return (ts, uid)

    members.sort(key=_sort_key)
    new_owner_uid = members[0][0]

    db = repo.db

    @firestore.transactional
    def _txn(txn):
        txn.update(repo.board_security_ref(board_id), {"ownerUid": new_owner_uid})
        txn.set(
            repo.member_ref(board_id, new_owner_uid),
            {"role": MemberRole.OWNER.value}, merge=True,
        )
        txn.delete(repo.member_ref(board_id, owner_uid))
        board_title = (repo.board_ref(board_id).get().to_dict() or {}).get("title", "")
        txn.set(
            repo.board_ref_doc(new_owner_uid, board_id),
            {
                "boardId": board_id,
                "title": board_title,
                "role": MemberRole.OWNER.value,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    _txn(db.transaction())
    repo.board_ref_doc(owner_uid, board_id).delete()
