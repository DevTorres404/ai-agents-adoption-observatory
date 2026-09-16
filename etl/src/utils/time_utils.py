"""Zona horaria canónica del observatorio: America/Guayaquil (UTC-5, sin DST).

Convención horaria del stack (a partir de septiembre de 2026):
- America/Guayaquil es la zona canónica (UTC-5, sin horario de verano).
- TODO datetime NAIVE producido por el pipeline o leído de columnas
  `timestamp without time zone` representa hora DE ECUADOR.
- Los datetime tz-aware se usan solo como instantes absolutos
  (p. ej. columnas TIMESTAMPTZ) y se normalizan a Ecuador al persistir.
"""
from datetime import date, datetime

from zoneinfo import ZoneInfo

ECUADOR_TZ = ZoneInfo("America/Guayaquil")


def now_local() -> datetime:
    """datetime actual en hora de Ecuador (tz-aware)."""
    return datetime.now(ECUADOR_TZ)


def today_local() -> date:
    """Fecha actual en hora de Ecuador."""
    return now_local().date()


def to_ec_naive(dt: datetime) -> datetime:
    """Convierte a datetime NAIVE en hora de Ecuador.

    - Si `dt` es naive, ya representa hora de Ecuador (convención del
      stack) y se devuelve tal cual.
    - Si `dt` es tz-aware, se convierte a America/Guayaquil y se le quita
      el offset, preservando el instante.
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(ECUADOR_TZ).replace(tzinfo=None)