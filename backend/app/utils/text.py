"""Normalizacao de texto para busca e unicidade (DT12, RF31).

Busca por titulo ignora maiusculas e acentos. Normalizacao de nomes de modelo
e e-mails usa caixa e espacos colapsados.
"""

from __future__ import annotations

import unicodedata


def strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_search(value: str) -> str:
    """Para comparacao de busca: sem acento, minusculo, espacos colapsados."""
    return " ".join(strip_accents(value).casefold().split())


def normalize_name(value: str) -> str:
    """Para unicidade de nome de modelo: minusculo e espacos colapsados."""
    return " ".join(value.strip().casefold().split())


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())
