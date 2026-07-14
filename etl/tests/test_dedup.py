import unittest

import pandas as pd

from src.staging.stg_dedup import deduplicate_staging


class DeduplicationTest(unittest.TestCase):
    def test_same_source_entity_across_snapshots_keeps_latest_version(self):
        frame = pd.DataFrame([
            {
                "fuente": "catalogo",
                "plataforma": "Terminal / CLI",
                "id_origen_registro": "Codex:owner/repo",
                "nombre_agente": "Codex",
                "fecha_evento": "2025-01-01",
                "raw_file_id": 10,
                "cantidad_menciones": 4,
            },
            {
                "fuente": "catalogo",
                "plataforma": "Terminal / CLI",
                "id_origen_registro": "Codex:owner/repo",
                "nombre_agente": "Codex",
                "fecha_evento": "2025-03-01",
                "raw_file_id": 12,
                "cantidad_menciones": 7,
            },
        ])

        result, removed = deduplicate_staging(frame)

        self.assertEqual(removed, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["fecha_evento"], "2025-03-01")
        self.assertEqual(result.iloc[0]["cantidad_menciones"], 7)

    def test_distinct_source_ids_remain_distinct(self):
        frame = pd.DataFrame([
            {
                "fuente": "github",
                "plataforma": "GitHub",
                "id_origen_registro": source_id,
                "nombre_agente": "Cline",
                "fecha_evento": "2025-01-01",
                "raw_file_id": 1,
            }
            for source_id in ("101", "102")
        ])

        result, removed = deduplicate_staging(frame)

        self.assertEqual(removed, 0)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
