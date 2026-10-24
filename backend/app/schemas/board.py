"""Contratos de kanbans, colunas, cards, campos e modelos (secoes 4-7, 14.1)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import (
    MAX_BOARD_NAME,
    MAX_CARD_TITLE,
    MAX_COLUMN_NAME,
    MAX_FIELD_NAME,
    MAX_TEMPLATE_NAME,
    FieldType,
    MemberRole,
    StrictModel,
)

# ---------------- Boards ----------------


class BoardCreate(StrictModel):
    name: str = Field(min_length=1, max_length=MAX_BOARD_NAME)
    idempotencyKey: str | None = Field(default=None, max_length=200)


class BoardPatch(StrictModel):
    name: str = Field(min_length=1, max_length=MAX_BOARD_NAME)
    baseVersion: int


class BoardSummaryOut(StrictModel):
    boardId: str
    title: str
    role: MemberRole
    grantedAt: str | None = None


class BoardListResponse(StrictModel):
    boards: list[BoardSummaryOut]


class BoardOut(StrictModel):
    boardId: str
    title: str
    timezone: str
    version: int
    columnsOrderVersion: int
    role: MemberRole
    createdAt: str
    updatedAt: str


# ---------------- Columns ----------------


class ColumnCreate(StrictModel):
    title: str = Field(min_length=1, max_length=MAX_COLUMN_NAME)
    beforeColumnId: str | None = None
    afterColumnId: str | None = None


class ColumnPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_COLUMN_NAME)
    minimized: bool | None = None
    baseVersion: int


class ColumnReorder(StrictModel):
    columnId: str
    beforeColumnId: str | None = None
    afterColumnId: str | None = None


class ColumnOut(StrictModel):
    columnId: str
    title: str
    sortKey: str
    minimized: bool
    cardCount: int
    version: int


# ---------------- Checklist ----------------


class ChecklistItemIn(StrictModel):
    itemId: str | None = None
    text: str = Field(max_length=2000)
    checked: bool = False


class ChecklistItemOut(StrictModel):
    itemId: str
    text: str
    checked: bool
    sortKey: str


# ---------------- Fields ----------------


class FieldIn(StrictModel):
    """Operacao tipada de campo no salvamento do detalhe (secao 14.1, grupo Campos)."""

    fieldId: str | None = None  # None -> criar; informado -> editar/mover
    label: str = Field(min_length=1, max_length=MAX_FIELD_NAME)
    type: FieldType
    value: Any | None = None
    visibleOnBoard: bool = False
    isDeadline: bool = False
    # Ordem relativa informada pela posicao na lista enviada.


class FieldOut(StrictModel):
    fieldId: str
    label: str
    type: FieldType
    value: Any | None
    sortKey: str
    visibleOnBoard: bool
    isDeadline: bool
    semanticRole: str | None = None


# ---------------- Cards ----------------


class CardCreate(StrictModel):
    title: str = Field(min_length=1, max_length=MAX_CARD_TITLE)
    columnId: str
    templateId: str | None = None
    idempotencyKey: str | None = Field(default=None, max_length=200)


class CardSaveRequest(StrictModel):
    """PATCH do detalhe: salva titulo, campos e projecoes de forma consistente."""

    title: str = Field(min_length=1, max_length=MAX_CARD_TITLE)
    fields: list[FieldIn]
    contentVersion: int


class CardMoveRequest(StrictModel):
    targetColumnId: str
    beforeCardId: str | None = None
    afterCardId: str | None = None
    positionVersion: int


class CardDuplicateRequest(StrictModel):
    idempotencyKey: str | None = Field(default=None, max_length=200)


class VisibleFieldSnapshot(StrictModel):
    fieldId: str
    label: str
    type: FieldType
    value: Any | None
    isDeadline: bool
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class CardSummaryOut(StrictModel):
    cardId: str
    title: str
    columnId: str
    sortKey: str
    contentVersion: int
    positionVersion: int
    visibleFieldsSnapshot: list[VisibleFieldSnapshot]
    overdue: bool
    createdAt: str
    updatedAt: str


class CardDetailOut(StrictModel):
    cardId: str
    title: str
    columnId: str
    sortKey: str
    contentVersion: int
    positionVersion: int
    fields: list[FieldOut]
    createdAt: str
    updatedAt: str


# ---------------- Templates ----------------


class TemplateCreate(StrictModel):
    name: str = Field(min_length=1, max_length=MAX_TEMPLATE_NAME)
    fromCardId: str
    replaceExisting: bool = False


class TemplatePatch(StrictModel):
    name: str = Field(min_length=1, max_length=MAX_TEMPLATE_NAME)
    baseVersion: int


class TemplateOut(StrictModel):
    templateId: str
    name: str
    createdByUid: str
    version: int
    createdAt: str
    updatedAt: str
