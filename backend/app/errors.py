"""Erros de dominio e formato uniforme de resposta de erro (secao 14.2).

Formato: { "error": { "code", "message", "requestId", "details"? } }
Mensagens em pt BR. Nunca expor stack trace, dados de outra conta ou segredos.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Erro de dominio com codigo estavel e status HTTP."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Ocorreu um erro interno."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Requisicao invalida."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Autenticacao necessaria ou invalida."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Voce nao tem permissao para esta operacao."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Recurso nao encontrado."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Conflito de estado. Recarregue e tente novamente."


class VersionConflictError(ConflictError):
    code = "version_conflict"
    message = "O conteudo foi alterado por outra pessoa."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    message = "Arquivo ou corpo acima do limite permitido."


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Dados invalidos."


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Muitas tentativas. Aguarde e tente novamente."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Servico indisponivel no momento."


def error_body(
    code: str, message: str, request_id: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "requestId": request_id}}
    if details:
        body["error"]["details"] = details
    return body
