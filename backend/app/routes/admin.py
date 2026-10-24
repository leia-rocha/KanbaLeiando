"""Painel administrativo: sessao e gestao de usuarios (RF06-RF08, RF37)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.config import get_settings
from app.deps import get_repo, get_request_id, require_admin
from app.errors import ForbiddenError
from app.repositories import Repo
from app.schemas.admin import (
    AdminActionResponse,
    AdminLoginRequest,
    AdminSessionResponse,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserOut,
    AdminUserPatch,
)
from app.services import admin_session, admin_users, operations

router = APIRouter(prefix="/admin")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/session", response_model=AdminSessionResponse)
def admin_login(
    body: AdminLoginRequest,
    request: Request,
    response: Response,
    repo: Repo = Depends(get_repo),
) -> AdminSessionResponse:
    settings = get_settings()
    token, csrf, expires_at = admin_session.authenticate(
        repo, body.username, body.password, _client_ip(request)
    )
    response.set_cookie(
        key=admin_session.COOKIE_NAME,
        value=token,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
    )
    return AdminSessionResponse(csrfToken=csrf, expiresAt=expires_at)


@router.delete("/session")
def admin_logout(
    request: Request,
    response: Response,
    repo: Repo = Depends(get_repo),
) -> dict:
    token = request.cookies.get(admin_session.COOKIE_NAME)
    admin_session.revoke_session(repo, token)
    response.delete_cookie(admin_session.COOKIE_NAME, path="/")
    return {"message": "Sessao encerrada."}


@router.get("/users", response_model=AdminUserListResponse, dependencies=[Depends(require_admin)])
def list_users(
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    repo: Repo = Depends(get_repo),
) -> AdminUserListResponse:
    data = admin_users.list_users(repo, query=q, cursor=cursor, limit=min(limit, 100))
    return AdminUserListResponse(
        users=[AdminUserOut(**u) for u in data["users"]], nextCursor=data["nextCursor"]
    )


@router.post("/users", response_model=AdminUserOut, dependencies=[Depends(require_admin)])
def create_user(body: AdminUserCreate, repo: Repo = Depends(get_repo)) -> AdminUserOut:
    data = admin_users.create_user(repo, name=body.name, email=body.email)
    return AdminUserOut(**data["profile"])


@router.patch(
    "/users/{uid}", response_model=AdminUserOut, dependencies=[Depends(require_admin)]
)
def patch_user(uid: str, body: AdminUserPatch, repo: Repo = Depends(get_repo)) -> AdminUserOut:
    data = admin_users.patch_user(
        repo, uid, name=body.name, email=body.email, status=body.status
    )
    return AdminUserOut(**data)


@router.delete(
    "/users/{uid}", response_model=AdminActionResponse, dependencies=[Depends(require_admin)]
)
def delete_user(
    uid: str, repo: Repo = Depends(get_repo), rid: str = Depends(get_request_id)
) -> AdminActionResponse:
    # A conta administrativa de ambiente nao e usuario comum e nao pode ser excluida.
    if not repo.user_ref(uid).get().exists:
        raise ForbiddenError("Usuario nao encontrado ou nao administravel.")
    op_id = operations.start_user_deletion(repo, uid, actor_uid="admin")
    return AdminActionResponse(message="Exclusao em processamento.", operationId=op_id)


@router.post(
    "/users/{uid}/password-reset",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_admin)],
)
def password_reset(uid: str, repo: Repo = Depends(get_repo)) -> AdminActionResponse:
    state = admin_users.send_password_reset(repo, uid)
    return AdminActionResponse(message="Solicitacao de redefinicao processada.", emailState=state)


@router.post(
    "/users/{uid}/welcome-resend",
    response_model=AdminActionResponse,
    dependencies=[Depends(require_admin)],
)
def welcome_resend(uid: str, repo: Repo = Depends(get_repo)) -> AdminActionResponse:
    state = admin_users.resend_welcome(repo, uid)
    return AdminActionResponse(message="Reenvio de boas-vindas processado.", emailState=state)


@router.get(
    "/operations/{operation_id}", dependencies=[Depends(require_admin)]
)
def get_operation(operation_id: str, repo: Repo = Depends(get_repo)) -> dict:
    snap = repo.operation_ref(operation_id).get()
    if not snap.exists:
        return {"status": "not_found"}
    d = snap.to_dict() or {}
    return {"operationId": operation_id, "kind": d.get("kind"), "status": d.get("status")}
