"""Projecoes de leitura do card (secao 13.2, RF20, RF35).

O backend e o unico responsavel por reconstruir visibleFieldsSnapshot e dueFields
apos qualquer alteracao de ordem, valor, visibilidade ou exclusao. Nunca confiar
em projecao enviada pelo cliente.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import DEADLINE_CAPABLE, FieldType
from app.utils.timeutils import is_date_overdue, is_datetime_overdue

MAX_VISIBLE = 2


def build_projection(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Recebe os campos ordenados por sortKey e devolve a projecao do card.

    - visibleFieldIds: ate 2 ids marcados como visiveis, na ordem dos campos.
    - visibleFieldsSnapshot: label/type/valor completo + anexos de apresentacao.
    - dueFields: prazos preenchidos (inclusive de campos nao visiveis).
    """
    ordered = sorted(fields, key=lambda f: f.get("sortKey", ""))
    visible_ids: list[str] = []
    snapshot: list[dict[str, Any]] = []
    due_fields: list[dict[str, Any]] = []

    for field in ordered:
        ftype = field.get("type")
        is_deadline = bool(field.get("isDeadline")) and ftype in {
            FieldType.DATE.value,
            FieldType.DATETIME.value,
        }
        value = field.get("value")
        if is_deadline and value not in (None, "", []):
            due_fields.append(
                {"fieldId": field["fieldId"], "type": ftype, "value": value}
            )
        if field.get("visibleOnBoard") and len(visible_ids) < MAX_VISIBLE:
            visible_ids.append(field["fieldId"])
            snapshot.append(
                {
                    "fieldId": field["fieldId"],
                    "label": field.get("label", ""),
                    "type": ftype,
                    "value": value,
                    "isDeadline": is_deadline,
                    "attachments": field.get("attachmentsSnapshot", []),
                }
            )

    return {
        "visibleFieldIds": visible_ids,
        "visibleFieldsSnapshot": snapshot,
        "dueFields": due_fields,
    }


def compute_overdue(due_fields: list[dict[str, Any]], tz_name: str, now=None) -> bool:
    """Atraso: basta um prazo vencido entre os dueFields (RF30)."""
    for due in due_fields:
        value = due.get("value")
        if value in (None, "", []):
            continue
        if due.get("type") == FieldType.DATE.value and is_date_overdue(value, tz_name, now):
            return True
        if due.get("type") == FieldType.DATETIME.value and is_datetime_overdue(value, now):
            return True
    return False


def count_visible(fields: list[dict[str, Any]]) -> int:
    return sum(1 for f in fields if f.get("visibleOnBoard"))


def validate_visible_limit(fields: list[dict[str, Any]]) -> None:
    from app.errors import ValidationError

    if count_visible(fields) > MAX_VISIBLE:
        raise ValidationError(
            "No maximo dois campos podem ser visiveis no quadro.",
            code="too_many_visible_fields",
        )


def validate_deadline_marks(fields: list[dict[str, Any]]) -> None:
    from app.errors import ValidationError

    for field in fields:
        if field.get("isDeadline"):
            ftype = field.get("type")
            if ftype not in {t.value for t in DEADLINE_CAPABLE}:
                raise ValidationError(
                    "A marca de prazo so e permitida em campos DATA e DATA/HORA.",
                    code="deadline_on_invalid_type",
                )
