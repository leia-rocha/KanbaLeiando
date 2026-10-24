"""Contexto de requisicao: requestId e identidade resolvida."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import MemberRole, UserStatus


@dataclass
class CurrentUser:
    """Usuario comum autenticado e com perfil provisionado ativo."""

    uid: str
    email: str
    name: str
    status: UserStatus


@dataclass
class PublicVisitor:
    """Identidade tecnica de leitor publico (claims kind=public_view)."""

    uid: str
    board_id: str
    share_version: int


@dataclass
class BoardAccess:
    """Resultado de uma verificacao de acesso a um quadro."""

    board_id: str
    role: MemberRole | None  # None para leitor publico
    is_public: bool = False
