"""Tempo, fuso e calculo de atraso de prazos (secao 9.1, DT11).

- DATA (YYYY-MM-DD) vence quando comeca o dia seguinte no fuso do kanban.
- DATA/HORA (instante UTC) vence quando o instante atual supera o valor.
Usa timezone IANA (zoneinfo) para respeitar regras historicas de fuso.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso_utc(dt: datetime) -> str:
    """ISO 8601 em UTC, usado nos contratos da API (secao 14.1)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str) -> datetime:
    """Interpreta um instante ISO 8601. Aceita sufixo Z."""
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def parse_calendar_date(value: str) -> date:
    """Interpreta uma data de calendario YYYY-MM-DD."""
    return date.fromisoformat(value.strip())


def zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 - fuso invalido cai no padrao do produto
        return ZoneInfo("America/Sao_Paulo")


def date_due_instant_utc(cal_date: date, tz_name: str) -> datetime:
    """Instante UTC em que a DATA vence: inicio do dia seguinte no fuso informado.

    Ex.: 24/10/2026 vence quando comeca 25/10/2026 no fuso do kanban.
    """
    tz = zone(tz_name)
    next_day = cal_date + timedelta(days=1)
    start_next_day_local = datetime(
        next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=tz
    )
    return start_next_day_local.astimezone(UTC)


def is_date_overdue(cal_date_str: str, tz_name: str, now: datetime | None = None) -> bool:
    now = now or utc_now()
    try:
        cal_date = parse_calendar_date(cal_date_str)
    except ValueError:
        return False
    return now >= date_due_instant_utc(cal_date, tz_name)


def is_datetime_overdue(instant_iso: str, now: datetime | None = None) -> bool:
    now = now or utc_now()
    try:
        instant = parse_iso_datetime(instant_iso)
    except ValueError:
        return False
    return now > instant
