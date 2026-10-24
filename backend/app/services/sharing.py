"""Compartilhamento, membros e link publico (secao 10, RF32, RF33).

- Concessao de edicao por UID (nao pelo texto do e-mail). Repeticao nao duplica
  nem reinicia a antiguidade. E-mail nao cadastrado retorna orientacao (DT04).
- Link publico: token HMAC-SHA256 de boardId+shareVersion com PUBLIC_LINK_SECRET,
  base64url, comparado em tempo constante. Revogar/rotacionar incrementa versao.
- POST /public/session valida o token e emite Firebase custom token para uma
  identidade tecnica de visitante (kind=public_view, boardId, shareVersion).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from google.cloud import firestore

from app.clients import get_auth_client
from app.config import get_settings
from app.context import CurrentUser
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.repositories import Repo
from app.schemas.common import MemberRole, UserStatus
from app.services import audit
from app.services import authorization as authz
from app.utils.ids import new_public_visitor_uid
from app.utils.text import normalize_email
from app.utils.timeutils import to_iso_utc


def _ts(v) -> str:
    return to_iso_utc(v) if hasattr(v, "year") else ""


# ------------------------- Membros -------------------------


def list_members(repo: Repo, user: CurrentUser, board_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    sec = repo.board_security_ref(board_id).get().to_dict() or {}
    owner_uid = sec.get("ownerUid", "")
    members = []
    for doc in repo.members_col(board_id).stream():
        d = doc.to_dict() or {}
        profile = repo.user_ref(doc.id).get().to_dict() or {}
        members.append(
            {
                "uid": doc.id,
                "name": profile.get("name", ""),
                "email": profile.get("email", ""),
                "role": d.get("role", MemberRole.EDITOR.value),
                "grantedAt": _ts(d.get("grantedAt")),
            }
        )
    members.sort(key=lambda m: (m["role"] != MemberRole.OWNER.value, m["grantedAt"]))
    return {"members": members, "ownerUid": owner_uid}


def grant_editor(repo: Repo, user: CurrentUser, board_id: str, email: str,
                 request_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    norm = normalize_email(email)
    matches = list(
        repo.db.collection("users").where("normalizedEmail", "==", norm).limit(1).stream()
    )
    if not matches:
        # DT04: nao cria conta nem convite pendente.
        return {
            "message": "E-mail nao cadastrado.",
            "guidance": "Peca ao administrador para cadastrar este e-mail antes de compartilhar.",
        }
    target = matches[0]
    target_uid = target.id
    target_profile = target.to_dict() or {}
    status = target_profile.get("status")
    if status not in (UserStatus.ACTIVE.value, UserStatus.PENDING_ACTIVATION.value):
        raise ValidationError("Usuario nao esta ativo ou pendente.")

    member_ref = repo.member_ref(board_id, target_uid)
    existing = member_ref.get()
    if existing.exists:
        # Repetir compartilhamento nao duplica nem reinicia grantedAt (RF32).
        d = existing.to_dict() or {}
        return {
            "message": "Usuario ja possui edicao.",
            "member": _member_out(target_uid, target_profile, d),
        }

    member_ref.set(
        {
            "role": MemberRole.EDITOR.value,
            "grantedAt": firestore.SERVER_TIMESTAMP,
            "grantedByUid": user.uid,
        }
    )
    board_title = (repo.board_ref(board_id).get().to_dict() or {}).get("title", "")
    repo.board_ref_doc(target_uid, board_id).set(
        {
            "boardId": board_id,
            "title": board_title,
            "role": MemberRole.EDITOR.value,
            "grantedAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
    audit.record_now(
        repo, board_id=board_id, action="member.grant", entity_type="member",
        entity_id=target_uid, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id, changed_fields={"role": "editor"},
    )
    d = member_ref.get().to_dict() or {}
    return {"message": "Edicao concedida.", "member": _member_out(target_uid, target_profile, d)}


def revoke_editor(repo: Repo, user: CurrentUser, board_id: str, target_uid: str,
                  request_id: str) -> None:
    authz.require_board_owner(repo, board_id, user)
    sec = repo.board_security_ref(board_id).get().to_dict() or {}
    if sec.get("ownerUid") == target_uid:
        raise ForbiddenError("O dono nao pode ser removido.")
    repo.member_ref(board_id, target_uid).delete()
    repo.board_ref_doc(target_uid, board_id).delete()
    audit.record_now(
        repo, board_id=board_id, action="member.revoke", entity_type="member",
        entity_id=target_uid, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id,
    )


def _member_out(uid: str, profile: dict, member: dict) -> dict:
    return {
        "uid": uid,
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "role": member.get("role", MemberRole.EDITOR.value),
        "grantedAt": _ts(member.get("grantedAt")),
    }


# ------------------------- Link publico -------------------------


def _compute_token(board_id: str, share_version: int) -> str:
    settings = get_settings()
    msg = f"{board_id}:{share_version}".encode()
    digest = hmac.new(settings.public_link_secret.encode(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _public_url(board_id: str, token: str) -> str:
    settings = get_settings()
    return f"{settings.app_base_url.rstrip('/')}/s/{board_id}#token={token}"


def get_public_link(repo: Repo, user: CurrentUser, board_id: str) -> dict:
    authz.require_board_editor(repo, board_id, user)
    sec = repo.board_security_ref(board_id).get().to_dict() or {}
    enabled = bool(sec.get("publicEnabled", False))
    version = int(sec.get("publicShareVersion", 0))
    url = _public_url(board_id, _compute_token(board_id, version)) if enabled else None
    return {"enabled": enabled, "url": url, "shareVersion": version}


def rotate_public_link(repo: Repo, user: CurrentUser, board_id: str, request_id: str) -> dict:
    authz.require_board_owner(repo, board_id, user)
    ref = repo.board_security_ref(board_id)
    sec = ref.get().to_dict() or {}
    new_version = int(sec.get("publicShareVersion", 0)) + 1
    ref.update({"publicEnabled": True, "publicShareVersion": new_version})
    audit.record_now(
        repo, board_id=board_id, action="public_link.rotate", entity_type="board",
        entity_id=board_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id, changed_fields={"shareVersion": new_version},
    )
    url = _public_url(board_id, _compute_token(board_id, new_version))
    return {"enabled": True, "url": url, "shareVersion": new_version}


def revoke_public_link(repo: Repo, user: CurrentUser, board_id: str, request_id: str) -> dict:
    authz.require_board_owner(repo, board_id, user)
    ref = repo.board_security_ref(board_id)
    sec = ref.get().to_dict() or {}
    new_version = int(sec.get("publicShareVersion", 0)) + 1
    ref.update({"publicEnabled": False, "publicShareVersion": new_version})
    audit.record_now(
        repo, board_id=board_id, action="public_link.revoke", entity_type="board",
        entity_id=board_id, actor_uid=user.uid, actor_name=user.name,
        request_id=request_id,
    )
    return {"enabled": False, "url": None, "shareVersion": new_version}


def open_public_session(repo: Repo, board_id: str, token: str) -> dict:
    """Valida token do link e emite Firebase custom token de visitante."""
    sec_snap = repo.board_security_ref(board_id).get()
    if not sec_snap.exists:
        raise NotFoundError("Quadro indisponivel.")
    sec = sec_snap.to_dict() or {}
    if not sec.get("publicEnabled") or sec.get("status") == "deleting":
        raise NotFoundError("Acesso publico indisponivel.")
    version = int(sec.get("publicShareVersion", 0))
    expected = _compute_token(board_id, version)
    if not hmac.compare_digest(expected, token):
        raise ForbiddenError("Link publico invalido ou expirado.")

    visitor_uid = new_public_visitor_uid()
    auth = get_auth_client()
    custom_token = auth.create_custom_token(
        visitor_uid,
        {"kind": "public_view", "boardId": board_id, "shareVersion": version},
    )
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode()
    return {
        "customToken": custom_token,
        "boardId": board_id,
        "shareVersion": version,
        "scope": "public_view",
    }
