"""Geracao de identificadores opacos e aleatorios (secao 13.3).

IDs aleatorios evitam exposicao sequencial e concentracao de gravacoes.
"""

from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def new_id(prefix: str = "", length: int = 20) -> str:
    """ID aleatorio curto e url-safe. Prefixo opcional para legibilidade em logs."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    return f"{prefix}{body}" if prefix else body


def new_request_id() -> str:
    return "req_" + new_id(length=16)


def new_public_visitor_uid() -> str:
    """UID tecnico de visitante publico, com prefixo distinguivel (secao 10.3)."""
    return "public_" + new_id(length=24)
