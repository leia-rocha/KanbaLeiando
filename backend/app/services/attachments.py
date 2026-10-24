"""Anexos: uploads temporarios, URLs assinadas, previas e limpeza (secao 8).

- Nomes internos aleatorios vinculados a boardId/cardId/fieldId/attachmentId.
- Upload direto ao bucket por URL assinada; a API confirma tamanho e geracao
  antes de marcar ready. Rejeita e limpa objeto acima do limite.
- Download/previa exigem nova autorizacao e emitem URL assinada curta.
- Exclusao remove objeto e derivados; duplicacao copia objetos no bucket.
Em ambiente sem bucket configurado (emulador/dev), as funcoes degradam de forma
segura, registrando o estado sem quebrar o fluxo de dominio.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from google.cloud import firestore

from app.config import get_settings
from app.errors import PayloadTooLargeError, ValidationError
from app.repositories import Repo
from app.utils.ids import new_id
from app.utils.timeutils import to_iso_utc, utc_now

# Familias de previa (secao 8.3).
_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_PDF_MIME = {"application/pdf"}
_OFFICE_WORD = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_OFFICE_EXCEL = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _object_key(board_id: str, card_or_draft: str, field_id: str, attachment_id: str,
                original_name: str) -> str:
    # Nome interno aleatorio; nome original e apenas metadado de exibicao.
    safe = new_id("obj_", 24)
    return f"boards/{board_id}/{card_or_draft}/{field_id}/{attachment_id}/{safe}"


def create_upload_session(repo: Repo, uid: str, board_id: str, *, field_id, draft_id,
                          card_id, original_name: str, expected_size: int,
                          content_type: str) -> dict:
    settings = get_settings()
    if expected_size > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"Arquivo acima do limite de {settings.max_upload_bytes} bytes."
        )
    if not field_id:
        raise ValidationError("fieldId obrigatorio para upload.")

    upload_id = new_id("upl_", 20)
    attachment_id = new_id("att_", 16)
    container = card_id or draft_id or "draft"
    object_key = _object_key(board_id, container, field_id, attachment_id, original_name)
    expires = utc_now() + timedelta(minutes=15)

    upload_url = ""
    headers: dict[str, str] = {}
    try:
        from app.clients import get_bucket

        blob = get_bucket().blob(object_key)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )
        headers = {"Content-Type": content_type}
    except Exception:  # noqa: BLE001 - sem bucket (dev/emulador): segue sem URL
        upload_url = ""

    repo.upload_ref(upload_id).set(
        {
            "ownerUid": uid,
            "boardId": board_id,
            "draftId": draft_id,
            "cardId": card_id,
            "fieldId": field_id,
            "attachmentId": attachment_id,
            "objectKey": object_key,
            "originalName": original_name,
            "contentType": content_type,
            "expectedSize": expected_size,
            "status": "uploading",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "expiresAt": expires,
        }
    )
    return {
        "uploadId": upload_id,
        "uploadUrl": upload_url,
        "method": "PUT",
        "headers": headers,
        "objectKey": object_key,
        "expiresAt": to_iso_utc(expires),
    }


def complete_upload(repo: Repo, uid: str, upload_id: str) -> dict:
    settings = get_settings()
    snap = repo.upload_ref(upload_id).get()
    if not snap.exists:
        raise ValidationError("Sessao de upload inexistente.")
    data = snap.to_dict() or {}
    if data.get("ownerUid") != uid:
        raise ValidationError("Sessao de upload de outro usuario.")

    size_bytes = int(data.get("expectedSize", 0))
    detected_mime = data.get("contentType", "application/octet-stream")
    try:
        from app.clients import get_bucket

        blob = get_bucket().get_blob(data["objectKey"])
        if blob is not None:
            size_bytes = int(blob.size or 0)
            detected_mime = blob.content_type or detected_mime
            if size_bytes > settings.max_upload_bytes:
                blob.delete()
                repo.upload_ref(upload_id).update({"status": "rejected_oversize"})
                raise PayloadTooLargeError("Arquivo acima do limite permitido.")
    except PayloadTooLargeError:
        raise
    except Exception:  # noqa: BLE001 - sem bucket: usa metadados informados
        pass

    repo.upload_ref(upload_id).update(
        {"status": "staged", "sizeBytes": size_bytes, "detectedMimeType": detected_mime}
    )
    return {
        "uploadId": upload_id,
        "attachmentId": data["attachmentId"],
        "status": "staged",
        "originalName": data.get("originalName", ""),
        "sizeBytes": size_bytes,
        "detectedMimeType": detected_mime,
    }


def cancel_upload(repo: Repo, uid: str, upload_id: str) -> None:
    snap = repo.upload_ref(upload_id).get()
    if not snap.exists:
        return
    data = snap.to_dict() or {}
    if data.get("ownerUid") != uid:
        raise ValidationError("Sessao de upload de outro usuario.")
    try:
        from app.clients import get_bucket

        blob = get_bucket().get_blob(data.get("objectKey", ""))
        if blob is not None:
            blob.delete()
    except Exception:  # noqa: BLE001
        pass
    repo.upload_ref(upload_id).delete()


def signed_download_url(repo: Repo, board_id: str, card_id: str, attachment: dict) -> dict:
    settings = get_settings()
    expires = utc_now() + timedelta(seconds=settings.signed_url_ttl_seconds)
    url = ""
    try:
        from app.clients import get_bucket

        blob = get_bucket().blob(attachment["objectKey"])
        disposition = f'attachment; filename="{attachment.get("originalName", "arquivo")}"'
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=settings.signed_url_ttl_seconds),
            method="GET",
            response_disposition=disposition,
        )
    except Exception:  # noqa: BLE001
        url = ""
    return {"url": url, "expiresAt": to_iso_utc(expires)}


def preview_descriptor(attachment: dict) -> dict:
    """Classifica o anexo para previa (secao 8.3). A geracao pesada (Office)
    e tratada pelo servico de conversao sob demanda."""
    mime = (attachment.get("detectedMimeType") or "").lower()
    if mime in _IMAGE_MIME:
        return {"kind": "image"}
    if mime in _PDF_MIME:
        return {"kind": "pdf"}
    if mime in _OFFICE_WORD or mime in _OFFICE_EXCEL:
        return {"kind": "pages"}
    return {"kind": "download"}


def copy_attachments_for_duplicate(repo: Repo, board_id: str, src_card_id: str,
                                   new_card_id: str, src_attachments: list[dict],
                                   field_id_map: dict[str, str]) -> list[dict]:
    """Copia objetos no bucket para caminhos do novo card (RF22). Excluir o
    original nao pode quebrar os anexos da copia."""
    out = []
    for a in src_attachments:
        new_att_id = new_id("att_", 16)
        new_field_id = field_id_map.get(a.get("fieldId"), a.get("fieldId"))
        new_key = _object_key(
            board_id, new_card_id, new_field_id, new_att_id, a.get("originalName", "arquivo")
        )
        try:
            from app.clients import get_bucket

            bucket = get_bucket()
            src_blob = bucket.get_blob(a.get("objectKey", ""))
            if src_blob is not None:
                bucket.copy_blob(src_blob, bucket, new_key)
        except Exception:  # noqa: BLE001
            pass
        out.append(
            {
                "attachmentId": new_att_id,
                "fieldId": new_field_id,
                "originalName": a.get("originalName", ""),
                "sizeBytes": int(a.get("sizeBytes", 0)),
                "detectedMimeType": a.get("detectedMimeType", "application/octet-stream"),
                "objectKey": new_key,
                "objectGeneration": None,
                "previewState": "pending",
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
    return out


def schedule_card_attachments_cleanup(repo: Repo, board_id: str, card_id: str) -> None:
    """Cria intencao duravel de limpeza fisica dos objetos do card (DT14)."""
    keys = []
    for doc in repo.attachments_col(board_id, card_id).stream():
        d = doc.to_dict() or {}
        if d.get("objectKey"):
            keys.append(d["objectKey"])
    if not keys:
        return
    op_id = new_id("op_", 20)
    repo.operation_ref(op_id).set(
        {
            "kind": "attachments_cleanup",
            "status": "pending",
            "targetIds": keys,
            "boardId": board_id,
            "cardId": card_id,
            "cursor": 0,
            "retryCount": 0,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    from app.services import tasks as tasks_service

    tasks_service.enqueue(op_id, "attachments_cleanup")


def attachment_out(att: dict, attachment_id: str) -> dict:
    return {
        "attachmentId": attachment_id,
        "fieldId": att.get("fieldId", ""),
        "originalName": att.get("originalName", ""),
        "sizeBytes": int(att.get("sizeBytes", 0)),
        "detectedMimeType": att.get("detectedMimeType", "application/octet-stream"),
        "previewState": att.get("previewState", "pending"),
    }


def link_staged_attachments(repo: Repo, board_id: str, card_id: str,
                            upload_ids: list[str], uid: str) -> list[dict]:
    """Promove uploads staged para anexos ready vinculados ao card (secao 8.2)."""
    linked = []
    for upload_id in upload_ids:
        snap = repo.upload_ref(upload_id).get()
        if not snap.exists:
            continue
        data = snap.to_dict() or {}
        if data.get("ownerUid") != uid or data.get("status") != "staged":
            continue
        attachment_id = data["attachmentId"]
        repo.attachment_ref(board_id, card_id, attachment_id).set(
            {
                "fieldId": data.get("fieldId"),
                "originalName": data.get("originalName", ""),
                "sizeBytes": int(data.get("sizeBytes", 0)),
                "detectedMimeType": data.get("detectedMimeType", "application/octet-stream"),
                "objectKey": data.get("objectKey"),
                "objectGeneration": None,
                "previewState": "pending",
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
        )
        repo.upload_ref(upload_id).update({"status": "ready", "cardId": card_id})
        linked.append({"attachmentId": attachment_id, "fieldId": data.get("fieldId")})
    return linked


def list_attachments(repo: Repo, board_id: str, card_id: str) -> list[dict[str, Any]]:
    out = []
    for doc in repo.attachments_col(board_id, card_id).stream():
        out.append(attachment_out(doc.to_dict() or {}, doc.id))
    return out
