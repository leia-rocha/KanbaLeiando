"""Enfileiramento de tarefas finitas no Cloud Tasks (secao 16.2, DT18).

Cada tarefa chama POST /internal/tasks/{kind} autenticado por OIDC da conta de
servico da fila. Em ambiente sem fila configurada (dev), a intencao duravel fica
registrada e pode ser processada manualmente/por teste; nao usa BackgroundTasks
como garantia de entrega.
"""

from __future__ import annotations

import json

from app.config import get_settings


def enqueue(operation_id: str, kind: str) -> bool:
    """Agenda uma tarefa HTTP com identidade deterministica. Retorna True se
    enfileirou de fato."""
    settings = get_settings()
    if not (settings.cloud_tasks_queue and settings.cloud_tasks_location):
        return False
    try:
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            settings.google_cloud_project,
            settings.cloud_tasks_location,
            settings.cloud_tasks_queue,
        )
        url = f"{settings.app_base_url.rstrip('/')}/api/v1/internal/tasks/{kind}"
        task = {
            "name": client.task_path(
                settings.google_cloud_project,
                settings.cloud_tasks_location,
                settings.cloud_tasks_queue,
                f"{kind}-{operation_id}",
            ),
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"operationId": operation_id, "kind": kind}).encode(),
                "oidc_token": {
                    "service_account_email": settings.tasks_service_account_email,
                    "audience": settings.tasks_audience or url,
                },
            },
        }
        client.create_task(request={"parent": parent, "task": task})
        return True
    except Exception:  # noqa: BLE001 - falha de fila nao derruba a operacao
        return False


def verify_oidc(authorization: str | None) -> bool:
    """Valida o token OIDC da conta de servico da fila (audience e issuer).

    Mesmo com acesso publico na camada da plataforma, o handler interno exige
    identidade esperada (secao 16.2).
    """
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    token = authorization.split(" ", 1)[1].strip()
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token

        audience = settings.tasks_audience or (
            f"{settings.app_base_url.rstrip('/')}/api/v1/internal/tasks"
        )
        claims = id_token.verify_oauth2_token(token, g_requests.Request(), audience)
        email = claims.get("email", "")
        if settings.tasks_service_account_email and email != settings.tasks_service_account_email:
            return False
        return True
    except Exception:  # noqa: BLE001
        return False
