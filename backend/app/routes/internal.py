"""Handlers internos de Cloud Tasks (secao 16.2).

Autenticado por OIDC da conta de servico da fila. So retorna 2xx apos a etapa
persistente concluir ou ja estar concluida.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.deps import get_repo
from app.errors import ForbiddenError
from app.repositories import Repo
from app.services import operations
from app.services import tasks as tasks_service

router = APIRouter(prefix="/internal")


@router.post("/tasks/{kind}")
def run_task(
    kind: str,
    body: dict,
    repo: Repo = Depends(get_repo),
    authorization: str | None = Header(default=None),
):
    if not tasks_service.verify_oidc(authorization):
        raise ForbiddenError("Identidade de tarefa nao autorizada.")
    operation_id = body.get("operationId")
    if not operation_id:
        return {"status": "ignored"}
    result = operations.run_operation(repo, operation_id)
    return {"kind": kind, **result}
