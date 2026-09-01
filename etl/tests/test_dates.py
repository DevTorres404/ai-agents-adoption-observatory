import unittest
from datetime import datetime, timezone

import pandas as pd

from src.staging.stg_dates import parse_dates
from src.staging.stg_normalize_columns import normalize_dataframe


class DatesTest(unittest.TestCase):
    def test_aidev_uses_first_activity_when_last_activity_is_missing(self):
        raw = pd.DataFrame([
            {
                "agent": "Codex",
                "full_name": "owner/repo",
                "pull_requests_count": 1,
                "last_activity": None,
                "first_activity": "2024-02-03T00:00:00Z",
            }
        ])

        normalized = normalize_dataframe(
            raw,
            {"fuente": "catalogo", "tipo_fuente": "archivo", "id": 1},
        )

        self.assertEqual(normalized.loc[0, "fecha_evento_raw"], "2024-02-03T00:00:00Z")

    def test_catalog_preserves_observed_last_activity(self):
        frame = pd.DataFrame([
            {
                "fuente": "catalogo",
                "fecha_evento_raw": "2025-08-19T23:30:00Z",
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            }
        ])

        result = parse_dates(frame)

        self.assertEqual(result.loc[0, "fecha_evento"], "2025-08-19")
        self.assertFalse(bool(result.loc[0, "is_imputed_date"]))

    def test_missing_date_uses_immutable_raw_load_date(self):
        frame = pd.DataFrame([
            {
                "fuente": "gnews",
                "fecha_evento_raw": None,
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            }
        ])

        first = parse_dates(frame.copy())
        second = parse_dates(frame.copy())

        self.assertEqual(first.loc[0, "fecha_evento"], "2026-07-14")
        self.assertTrue(bool(first.loc[0, "is_imputed_date"]))
        pd.testing.assert_frame_equal(first, second)

    def test_postgres_microsecond_fallback_uses_compatible_datetime_resolution(self):
        frame = pd.DataFrame([{
            "fuente": "github",
            "fecha_evento_raw": None,
            "fecha_carga_raw": datetime(2026, 8, 27, 12, 1, 2, 345678, tzinfo=timezone.utc),
        }])

        result = parse_dates(frame)

        self.assertEqual(result.loc[0, "fecha_evento"], "2026-08-27")
        self.assertTrue(bool(result.loc[0, "is_imputed_date"]))


if __name__ == "__main__":
    unittest.main()
