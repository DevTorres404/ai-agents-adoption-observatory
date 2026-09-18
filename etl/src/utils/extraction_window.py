"""Validated, inclusive requested windows; coverage remains source-dependent."""
from dataclasses import dataclass
from datetime import date

from src.utils.time_utils import today_local


@dataclass(frozen=True)
class ExtractionWindow:
    start: date
    end: date

    def as_dict(self):
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "inclusive": True}


def resolve_window(start=None, end=None, from_year=None, to_year=None,
                   default_start=None, default_end=None):
    if from_year is not None or to_year is not None:
        if start is not None or end is not None:
            raise ValueError("Use fechas o años, no ambos")
        if from_year is None or to_year is None:
            raise ValueError("Indique --from-year y --to-year")
        start, end = date(from_year, 1, 1), date(to_year, 12, 31)
    else:
        if (start is None) != (end is None):
            raise ValueError("Indique --start-date y --end-date")
        start = start or default_start or date(2023, 1, 1)
        end = end or default_end or today_local()
    start = date.fromisoformat(start) if isinstance(start, str) else start
    end = date.fromisoformat(end) if isinstance(end, str) else end
    if start > end:
        raise ValueError("El inicio no puede ser posterior al fin")
    return ExtractionWindow(start, end)


def require_annual_window(window):
    """Prevent a partial-year aggregate from replacing a complete annual cohort."""
    if (window.start.month, window.start.day) != (1, 1) or (
        (window.end.month, window.end.day) != (12, 31) and window.end != today_local()
    ):
        raise ValueError("AIDev requiere años completos (o el año actual hasta hoy); use --from-year/--to-year")
