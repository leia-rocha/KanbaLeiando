"""Testes das projecoes e invariantes de campo (RF20, RF21, RF29, RF30)."""

from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.schemas.common import FieldType
from app.services import projection


def _field(fid, ftype, value=None, visible=False, deadline=False, sort="m"):
    return {
        "fieldId": fid,
        "label": fid,
        "type": ftype,
        "value": value,
        "sortKey": sort,
        "visibleOnBoard": visible,
        "isDeadline": deadline,
    }


def test_no_maximo_dois_campos_visiveis_no_snapshot():
    fields = [
        _field("a", FieldType.TEXT_BLOCK.value, "x", visible=True, sort="a"),
        _field("b", FieldType.LINK.value, "https://y", visible=True, sort="b"),
        _field("c", FieldType.TEXT_BLOCK.value, "z", visible=True, sort="c"),
    ]
    proj = projection.build_projection(fields)
    assert len(proj["visibleFieldIds"]) == 2
    assert proj["visibleFieldIds"] == ["a", "b"]


def test_validacao_rejeita_terceiro_visivel():
    fields = [
        _field("a", FieldType.TEXT_BLOCK.value, visible=True),
        _field("b", FieldType.TEXT_BLOCK.value, visible=True),
        _field("c", FieldType.TEXT_BLOCK.value, visible=True),
    ]
    with pytest.raises(ValidationError):
        projection.validate_visible_limit(fields)


def test_prazo_so_em_data_e_datahora():
    with pytest.raises(ValidationError):
        projection.validate_deadline_marks(
            [_field("a", FieldType.TEXT_BLOCK.value, deadline=True)]
        )
    # DATA e DATA/HORA sao aceitos.
    projection.validate_deadline_marks(
        [
            _field("a", FieldType.DATE.value, deadline=True),
            _field("b", FieldType.DATETIME.value, deadline=True),
        ]
    )


def test_due_fields_inclui_campos_nao_visiveis():
    fields = [
        _field("a", FieldType.DATE.value, "2026-01-01", visible=False, deadline=True),
    ]
    proj = projection.build_projection(fields)
    assert len(proj["dueFields"]) == 1
    assert proj["dueFields"][0]["fieldId"] == "a"


def test_overdue_basta_um_prazo_vencido():
    from datetime import datetime, timezone

    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    due = [
        {"fieldId": "a", "type": FieldType.DATE.value, "value": "2020-01-01"},
        {"fieldId": "b", "type": FieldType.DATE.value, "value": "2099-01-01"},
    ]
    assert projection.compute_overdue(due, "America/Sao_Paulo", now) is True
