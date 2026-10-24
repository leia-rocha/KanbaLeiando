"""Testes de calculo de prazo e fuso (RF29, RF30, DT11)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.utils.timeutils import (
    date_due_instant_utc,
    is_date_overdue,
    is_datetime_overdue,
    parse_calendar_date,
)


def test_date_vence_no_inicio_do_dia_seguinte_no_fuso():
    # 24/10/2026 vence quando comeca 25/10/2026 em America/Sao_Paulo (UTC-3).
    cal = parse_calendar_date("2026-10-24")
    due = date_due_instant_utc(cal, "America/Sao_Paulo")
    assert due == datetime(2026, 10, 25, 3, 0, tzinfo=timezone.utc)


def test_date_nao_vencida_antes_do_fim_do_dia():
    now = datetime(2026, 10, 24, 23, 0, tzinfo=timezone.utc)  # 20h em SP
    assert is_date_overdue("2026-10-24", "America/Sao_Paulo", now) is False


def test_date_vencida_apos_virada():
    now = datetime(2026, 10, 25, 3, 30, tzinfo=timezone.utc)  # 00h30 em SP do dia 25
    assert is_date_overdue("2026-10-24", "America/Sao_Paulo", now) is True


def test_datetime_vence_no_instante():
    instant = "2026-10-24T18:00:00Z"
    before = datetime(2026, 10, 24, 17, 59, tzinfo=timezone.utc)
    after = datetime(2026, 10, 24, 18, 1, tzinfo=timezone.utc)
    assert is_datetime_overdue(instant, before) is False
    assert is_datetime_overdue(instant, after) is True


def test_valor_invalido_nao_marca_atraso():
    assert is_date_overdue("data-invalida", "America/Sao_Paulo") is False
    assert is_datetime_overdue("nao-e-instante") is False
