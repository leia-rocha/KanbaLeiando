"""Gestao de contas pelo painel administrativo (RF03, RF05, RF06, RF37).

Provisiona identidade Firebase + perfil de aplicacao, atualiza, desativa/reativa
e exclui usuarios. A exclusao analisa a propriedade dos kanbans e transfere ou
remove conforme RF37, delegando a limpeza pesada a operacoes duraveis.
"""

from __future__ import annotations

import secrets

from google.cloud import firestore

from app.clients import get_auth_client
from app.errors import ConflictError, NotFoundError, ValidationError
from app.repositories import Repo
from app.schemas.common import UserStatus
from app.services import email as email_service
from app.utils.text import normalize_email
from app.utils.timeutils import to_iso_utc


def _profile_out(uid: str, data: dict) -> dict:
    return {
        "uid": uid,
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "status": data.get("status", UserStatus.PENDING_ACTIVATION.value),
        "createdAt": _ts(data.get("createdAt")),
        "updatedAt": _ts(data.get("updatedAt")),
        "lastWelcomeState": data.get("lastWelcomeState"),
    }


def _ts(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "year"):
        return to_iso_utc(value)
    return str(value)


def list_users(repo: Repo, *, query: str | None, cursor: str | None, limit: int) -> dict:
    col = repo.db.collection("users").order_by("normalizedEmail").limit(limit + 1)
    if cursor:
        col = col.start_after({"normalizedEmail": cursor})
    docs = list(col.stream())
    users = []
    for doc in docs[:limit]:
        data = doc.to_dict() or {}
        if query:
            q = normalize_email(query)
            if q not in data.get("normalizedEmail", "") and q not in data.get(
                "name", ""
            ).casefold():
                continue
        users.append(_profile_out(doc.id, data))
    next_cursor = None
    if len(docs) > limit:
        next_cursor = (docs[limit - 1].to_dict() or {}).get("normalizedEmail")
    return {"users": users, "nextCursor": next_cursor}


def create_user(repo: Repo, *, name: str, email: str) -> dict:
    """Cria identidade Firebase com senha aleatoria de alta entropia (nao persistida)
    e perfil pending_activation. Envia boas-vindas."""
    auth = get_auth_client()
    norm_email = normalize_email(email)

    existing = (
        repo.db.collection("users").where("normalizedEmail", "==", norm_email).limit(1).stream()
    )
    if any(True for _ in existing):
        raise ConflictError("Ja existe um usuario com este e-mail.", code="email_duplicate")

    random_password = secrets.token_urlsafe(32)
    try:
        fb_user = auth.create_user(
            email=email, password=random_password, display_name=name, email_verified=False
        )
    except Exception as exc:  # noqa: BLE001
        raise ConflictError(
            "Nao foi possivel criar a identidade no Firebase.", code="email_duplicate"
        ) from exc

    uid = fb_user.uid
    welcome_state = "sent"
    try:
        email_service.send_welcome_email(name, email)
    except email_service.EmailNotConfigured:
        welcome_state = "pending_no_smtp"
    except Exception:  # noqa: BLE001 - registra falha sem derrubar criacao
        welcome_state = "failed"

    repo.user_ref(uid).set(
        {
            "name": name,
            "email": email,
            "normalizedEmail": norm_email,
            "status": UserStatus.PENDING_ACTIVATION.value,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "lastWelcomeState": welcome_state,
        }
    )
    snap = repo.user_ref(uid).get()
    return {"profile": _profile_out(uid, snap.to_dict() or {}), "welcomeState": welcome_state}


def patch_user(repo: Repo, uid: str, *, name, email, status) -> dict:
    auth = get_auth_client()
    ref = repo.user_ref(uid)
    snap = ref.get()
    if not snap.exists:
        raise NotFoundError("Usuario nao encontrado.")
    data = snap.to_dict() or {}
    updates: dict = {"updatedAt": firestore.SERVER_TIMESTAMP}

    if name is not None:
        updates["name"] = name
        try:
            auth.update_user(uid, display_name=name)
        except Exception:  # noqa: BLE001
            pass

    if email is not None and normalize_email(email) != data.get("normalizedEmail"):
        norm = normalize_email(email)
        dup = repo.db.collection("users").where("normalizedEmail", "==", norm).limit(1).stream()
        if any(d.id != uid for d in dup):
            raise ConflictError("E-mail ja utilizado por outra conta.", code="email_duplicate")
        try:
            auth.update_user(uid, email=email)  # preserva o UID
        except Exception as exc:  # noqa: BLE001
            raise ConflictError("Conflito ao atualizar e-mail.", code="email_duplicate") from exc
        updates["email"] = email
        updates["normalizedEmail"] = norm

    if status is not None:
        new_status = UserStatus(status)
        if new_status not in (UserStatus.ACTIVE, UserStatus.DISABLED):
            raise ValidationError("Status administravel invalido.")
        updates["status"] = new_status.value
        try:
            auth.update_user(uid, disabled=(new_status == UserStatus.DISABLED))
            if new_status == UserStatus.DISABLED:
                auth.revoke_refresh_tokens(uid)
        except Exception:  # noqa: BLE001
            pass

    ref.update(updates)
    return _profile_out(uid, (ref.get().to_dict() or {}))


def send_password_reset(repo: Repo, uid: str) -> str:
    snap = repo.user_ref(uid).get()
    if not snap.exists:
        raise NotFoundError("Usuario nao encontrado.")
    data = snap.to_dict() or {}
    try:
        email_service.send_password_reset_email(data.get("name", ""), data.get("email", ""))
        return "sent"
    except email_service.EmailNotConfigured:
        return "pending_no_smtp"
    except Exception:  # noqa: BLE001
        repo.user_ref(uid).update({"lastWelcomeState": "reset_failed"})
        return "failed"


def resend_welcome(repo: Repo, uid: str) -> str:
    snap = repo.user_ref(uid).get()
    if not snap.exists:
        raise NotFoundError("Usuario nao encontrado.")
    data = snap.to_dict() or {}
    if data.get("status") != UserStatus.PENDING_ACTIVATION.value:
        raise ConflictError("Usuario nao esta pendente de primeiro acesso.")
    try:
        email_service.send_welcome_email(data.get("name", ""), data.get("email", ""))
        state = "sent"
    except email_service.EmailNotConfigured:
        state = "pending_no_smtp"
    except Exception:  # noqa: BLE001
        state = "failed"
    repo.user_ref(uid).update({"lastWelcomeState": state})
    return state
