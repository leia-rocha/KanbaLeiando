"""Compartilhamento, link publico e auditoria (RF32-RF34)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_repo, get_request_id
from app.repositories import Repo
from app.schemas.sharing import (
    AuditListResponse,
    GrantResponse,
    MemberGrantRequest,
    MemberListResponse,
    MemberOut,
    PublicLinkOut,
)
from app.services import audit_read
from app.services import sharing as sharing_service

router = APIRouter(prefix="/boards/{board_id}")


@router.get("/members", response_model=MemberListResponse)
def list_members(board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    data = sharing_service.list_members(repo, user, board_id)
    return MemberListResponse(
        members=[MemberOut(**m) for m in data["members"]], ownerUid=data["ownerUid"]
    )


@router.post("/members", response_model=GrantResponse)
def grant_member(
    board_id: str,
    body: MemberGrantRequest,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    data = sharing_service.grant_editor(repo, user, board_id, body.email, rid)
    member = MemberOut(**data["member"]) if data.get("member") else None
    return GrantResponse(message=data["message"], member=member, guidance=data.get("guidance"))


@router.delete("/members/{uid}", status_code=204)
def revoke_member(
    board_id: str,
    uid: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    sharing_service.revoke_editor(repo, user, board_id, uid, rid)


@router.get("/public-link", response_model=PublicLinkOut)
def get_public_link(board_id: str, user=Depends(get_current_user), repo: Repo = Depends(get_repo)):
    return PublicLinkOut(**sharing_service.get_public_link(repo, user, board_id))


@router.post("/public-link/rotate", response_model=PublicLinkOut)
def rotate_public_link(
    board_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    return PublicLinkOut(**sharing_service.rotate_public_link(repo, user, board_id, rid))


@router.post("/public-link/revoke", response_model=PublicLinkOut)
def revoke_public_link(
    board_id: str,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
    rid: str = Depends(get_request_id),
):
    return PublicLinkOut(**sharing_service.revoke_public_link(repo, user, board_id, rid))


@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    board_id: str,
    cursor: str | None = None,
    limit: int = 50,
    user=Depends(get_current_user),
    repo: Repo = Depends(get_repo),
):
    data = audit_read.list_events(repo, user, board_id, cursor, limit)
    return AuditListResponse(events=data["events"], nextCursor=data["nextCursor"])
