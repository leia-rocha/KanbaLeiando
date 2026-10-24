"""Dependencias FastAPI: requestId, repo, usuario atual, visitante, admin."""

from __future__ import annotations

from fastapi import Depends, Header, Request

from app.context import CurrentUser, PublicVisitor
from app.repositories import Repo
from app.services import admin_session
from app.services import authorization as authz
from app.utils.ids import new_request_id


def get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = new_request_id()
        request.state.request_id = rid
    return rid


def get_repo() -> Repo:
    return Repo()


def get_current_user(
    authorization: str | None = Header(default=None),
    repo: Repo = Depends(get_repo),
) -> CurrentUser:
    return authz.resolve_current_user(repo, authorization)


def get_public_visitor(
    authorization: str | None = Header(default=None),
    repo: Repo = Depends(get_repo),
) -> PublicVisitor:
    return authz.resolve_public_visitor(repo, authorization)


def require_admin(
    request: Request,
    repo: Repo = Depends(get_repo),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    """Valida sessao administrativa. Mutacoes exigem CSRF (validado no router)."""
    token = request.cookies.get(admin_session.COOKIE_NAME)
    method = request.method.upper()
    admin_session.validate_session(
        repo, token, x_csrf_token, require_csrf=method not in ("GET", "HEAD", "OPTIONS")
    )
