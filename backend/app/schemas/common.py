"""Tipos e limites compartilhados dos contratos (secao 6.2)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

# Limites de texto (secao 6.2)
MAX_FIELD_NAME = 120
MAX_CARD_TITLE = 200
MAX_BOARD_NAME = 200
MAX_COLUMN_NAME = 120
MAX_TEMPLATE_NAME = 120
# Limite tecnico de armazenamento por valor de campo: 100 KiB de JSON UTF-8.
MAX_FIELD_VALUE_BYTES = 100 * 1024


class StrictModel(BaseModel):
    """Base que rejeita propriedades inesperadas (secao 14.1)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class FieldType(str, Enum):
    TEXT_BLOCK = "TEXT_BLOCK"
    LINK = "LINK"
    ATTACHMENT = "ATTACHMENT"
    DATE = "DATE"
    DATETIME = "DATETIME"
    CHECKLIST = "CHECKLIST"


# Tipos que aceitam a marca de prazo (RF29).
DEADLINE_CAPABLE = {FieldType.DATE, FieldType.DATETIME}


class MemberRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"


class UserStatus(str, Enum):
    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETING = "deleting"


class Pagination(StrictModel):
    cursor: str | None = None
    limit: int = 50
