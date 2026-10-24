"""Autorizacao da API (secao 3.1, 15.1).

O Firebase Admin SDK ignora as Security Rules, entao todo servico de dominio
aplica autorizacao propria: valida o ID token, consulta o perfil de aplicacao em
cada operacao protegida e confirma o vinculo com o quadro. Tambem confirma que
boardId/columnId/cardId/fieldId/attachmentId pertencem a mesma arvore (prevencao
de troca de identificadores).
"""

from __future__ import annotations

from app.clients import get_auth_client
from app.context import CurrentUser, PublicVisitor
from app.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.repositories import Repo
from app.schemas.common import MemberRole, UserStatus

# A rota de ativacao e a unica que aceita perfil pending_activation (RF03).
_ACTIVATION_ALLOWED = {UserStatus.PENDING_ACTIVATION, UserStatus.ACTIVE}


def verify_id_token(authorization: str | None) -> dict:
    """Valida o Bearer ID token com o Admin SDK (projeto, assinatura, expiracao,
    revogacao). Retorna as claims decodificadas."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Token de autenticacao ausente.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedError("Token de autenticacao ausente.")
    auth = get_auth_client()
    try:
        return auth.verify_id_token(token, check_revoked=True)
    except Exception as exc:  # noqa: BLE001 - normaliza qualquer falha de token
        raise UnauthorizedError("Token invalido ou expirado.") from exc


def load_profile(repo: Repo, uid: str) -> dict | None:
    snap = repo.user_ref(uid).get()
    return snap.to_dict() if snap.exists else None


def resolve_current_user(repo: Repo, authorization: str | None) -> CurrentUser:
    """Usuario comum ativo. Rejeita desativado, em exclusao, ausente ou pendente."""
    claims = verify_id_token(authorization)
    uid = claims.get("uid") or claims.get("sub")
    if claims.get("kind") == "public_view":
        raise ForbiddenError("Credencial publica nao acessa rotas privadas.")
    profile = load_profile(repo, uid) if uid else None
    if not profile:
        # Identidade criada direto no provedor nao recebe acesso (RF02).
        raise ForbiddenError("Perfil de usuario nao provisionado.")
    status = UserStatus(profile.get("status", UserStatus.DISABLED.value))
    if status != UserStatus.ACTIVE:
        raise ForbiddenError("Conta sem acesso ativo.")
    return CurrentUser(
        uid=uid,
        email=profile.get("email", ""),
        name=profile.get("name", ""),
        status=status,
    )


def resolve_activation_identity(repo: Repo, authorization: str | None) -> tuple[str, dict]:
    """Excecao de RF03: aceita perfil pending_activation, exige auth recente por
    password e identidade do mesmo UID provisionado."""
    claims = verify_id_token(authorization)
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise UnauthorizedError("Token invalido.")
    sign_in = claims.get("firebase", {}).get("sign_in_provider")
    if sign_in != "password":
        raise ForbiddenError("Ativacao exige autenticacao por e-mail e senha.")
    profile = load_profile(repo, uid)
    if not profile:
        raise ForbiddenError("Perfil nao provisionado.")
    status = UserStatus(profile.get("status", UserStatus.DISABLED.value))
    if status not in _ACTIVATION_ALLOWED:
        raise ForbiddenError("Conta nao elegivel a ativacao.")
    return uid, profile


def resolve_public_visitor(repo: Repo, authorization: str | None) -> PublicVisitor:
    """Leitor publico: claims kind=public_view, boardId e shareVersion."""
    claims = verify_id_token(authorization)
    if claims.get("kind") != "public_view":
        raise ForbiddenError("Credencial nao e de leitor publico.")
    board_id = claims.get("boardId")
    share_version = claims.get("shareVersion")
    uid = claims.get("uid") or claims.get("sub")
    if not board_id or share_version is None:
        raise ForbiddenError("Credencial publica incompleta.")
    # A versao da claim deve continuar igual a versao vigente do board.
    sec = repo.board_security_ref(board_id).get()
    if not sec.exists:
        raise NotFoundError("Quadro indisponivel.")
    sec_data = sec.to_dict() or {}
    if not sec_data.get("publicEnabled"):
        raise ForbiddenError("Acesso publico desativado.")
    if int(sec_data.get("publicShareVersion", -1)) != int(share_version):
        raise ForbiddenError("Link publico expirado. Solicite um novo.")
    if sec_data.get("status") == "deleting":
        raise NotFoundError("Quadro indisponivel.")
    return PublicVisitor(uid=uid, board_id=board_id, share_version=int(share_version))


def get_board_role(repo: Repo, board_id: str, uid: str) -> MemberRole | None:
    member = repo.member_ref(board_id, uid).get()
    if not member.exists:
        return None
    data = member.to_dict() or {}
    role = data.get("role")
    return MemberRole(role) if role in (MemberRole.OWNER.value, MemberRole.EDITOR.value) else None


def require_board_editor(repo: Repo, board_id: str, user: CurrentUser) -> MemberRole:
    """Dono ou editor. Qualquer outra situacao e 403/404."""
    sec = repo.board_security_ref(board_id).get()
    if not sec.exists or (sec.to_dict() or {}).get("status") == "deleting":
        raise NotFoundError("Quadro nao encontrado.")
    role = get_board_role(repo, board_id, user.uid)
    if role is None:
        raise ForbiddenError("Voce nao participa deste quadro.")
    return role


def require_board_owner(repo: Repo, board_id: str, user: CurrentUser) -> None:
    role = require_board_editor(repo, board_id, user)
    if role != MemberRole.OWNER:
        raise ForbiddenError("Apenas o dono pode executar esta operacao.")


def assert_card_in_board(repo: Repo, board_id: str, card_id: str) -> dict:
    snap = repo.card_ref(board_id, card_id).get()
    if not snap.exists:
        raise NotFoundError("Card nao encontrado.")
    return snap.to_dict() or {}


def assert_field_in_card(repo: Repo, board_id: str, card_id: str, field_id: str) -> dict:
    snap = repo.field_ref(board_id, card_id, field_id).get()
    if not snap.exists:
        raise NotFoundError("Campo nao encontrado.")
    return snap.to_dict() or {}


def assert_attachment_in_card(
    repo: Repo, board_id: str, card_id: str, attachment_id: str
) -> dict:
    snap = repo.attachment_ref(board_id, card_id, attachment_id).get()
    if not snap.exists:
        raise NotFoundError("Anexo nao encontrado.")
    return snap.to_dict() or {}
