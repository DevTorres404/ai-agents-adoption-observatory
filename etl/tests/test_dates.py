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

    def test_mixed_naive_and_aware_dates_keep_real_fecha(self):
        # Regression: Staging concatena fuentes con convenciones de fecha
        # distintas (naive y tz-aware) en UNA columna antes de parsear.
        # Un pd.to_datetime(utc=True) vectorizado vuelve NaT a uno de los
        # dos grupos en pandas>=3.0; el parseo por valor debe conservar
        # ambas fechas y no imputar a la fecha de carga del archivo Raw.
        frame = pd.DataFrame([
            {
                "fuente": "arxiv",
                "fecha_evento_raw": "2024-02-03T12:30:00+00:00",
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            },
            {
                "fuente": "google_trends",
                "fecha_evento_raw": "2023-01-22T00:00:00",
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            },
            {
                "fuente": "stackoverflow",
                "fecha_evento_raw": "2026-08-22T02:58:42",
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            },
            {
                "fuente": "devto",
                "fecha_evento_raw": "2026-09-13T07:06:59Z",
                "fecha_carga_raw": "2026-07-14T01:00:00Z",
            },
        ])

        result = parse_dates(frame)

        self.assertEqual(result.loc[0, "fecha_evento"], "2024-02-03")
        self.assertFalse(bool(result.loc[0, "is_imputed_date"]))
        self.assertEqual(result.loc[1, "fecha_evento"], "2023-01-22")
        self.assertFalse(bool(result.loc[1, "is_imputed_date"]))
        self.assertEqual(result.loc[2, "fecha_evento"], "2026-08-22")
        self.assertFalse(bool(result.loc[2, "is_imputed_date"]))
        self.assertEqual(result.loc[3, "fecha_evento"], "2026-09-13")
        self.assertFalse(bool(result.loc[3, "is_imputed_date"]))

    def test_google_trends_raw_fecha_flows_to_fecha_evento(self):
        # Ruta completa del pipeline para google_trends: el campo crudo
        # `fecha` debe alimentar fecha_evento (2023..2026 real), nunca la
        # fecha de carga del archivo Raw, aun concatenado con una fuente
        # tz-aware (comportamiento del bug 2026-09-16: 1.940 filas -> 2026).
        raw_trends = pd.DataFrame([
            {"agente": "Devin AI", "fecha": "2023-01-22T00:00:00", "valor": 0},
            {"agente": "Devin AI", "fecha": "2025-06-15T00:00:00", "valor": 4},
            {"agente": "Devin AI", "fecha": "2026-03-02T00:00:00", "valor": 10},
        ])
        raw_arxiv = pd.DataFrame([
            {"id": "1", "title": "t", "description": "d", "url": "u",
             "created_at": "2024-05-01T10:00:00+00:00", "categories": ["cs.AI"]},
        ])

        trends_norm = normalize_dataframe(
            raw_trends,
            {"fuente": "google_trends", "tipo_fuente": "google_trends",
             "id": 7, "fecha_carga": "2026-07-14T01:00:00Z"},
        )
        arxiv_norm = normalize_dataframe(
            raw_arxiv,
            {"fuente": "arxiv", "tipo_fuente": "arxiv",
             "id": 8, "fecha_carga": "2026-07-14T01:00:00Z"},
        )
        merged = pd.concat([arxiv_norm, trends_norm], ignore_index=True)

        result = parse_dates(merged)
        trends = result[result["fuente"] == "google_trends"].reset_index(drop=True)

        self.assertEqual(trends.loc[0, "fecha_evento"], "2023-01-22")
        self.assertEqual(trends.loc[1, "fecha_evento"], "2025-06-15")
        self.assertEqual(trends.loc[2, "fecha_evento"], "2026-03-02")
        self.assertFalse(bool(trends["is_imputed_date"].any()))
        self.assertEqual(
            result.loc[result["fuente"] == "arxiv", "fecha_evento"].iloc[0],
            "2024-05-01",
        )


if __name__ == "__main__":
    unittest.main()