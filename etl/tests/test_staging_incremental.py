import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from src.staging.stg_build_unified import (
    TRANSFORMATION_VERSION,
    build_staging_upsert_sql,
    plan_staging_files,
)


UPSERT_TEST_COLUMNS = [
    "fuente",
    "plataforma",
    "id_origen_registro",
    "nombre_agente",
    "fecha_evento",
    "raw_file_id",
    "raw_record_id",
    "transformation_version",
]


class IncrementalStagingTest(unittest.TestCase):
    def test_rerun_is_idempotent_for_already_processed_files(self):
        selected = plan_staging_files(
            available_file_ids=[1, 2],
            processed_file_ids=[1, 2],
            stored_versions=[TRANSFORMATION_VERSION],
            rebuild=False,
        )

        self.assertEqual(selected, [])

    def test_partial_snapshot_absence_does_not_schedule_deletion(self):
        selected = plan_staging_files(
            available_file_ids=[3],
            processed_file_ids=[1, 2],
            stored_versions=[TRANSFORMATION_VERSION],
            rebuild=False,
        )

        self.assertEqual(selected, [3])
        sql = build_staging_upsert_sql(UPSERT_TEST_COLUMNS)
        self.assertNotIn("DELETE", sql.upper())
        self.assertNotIn("TRUNCATE", sql.upper())

    def test_version_change_requires_explicit_rebuild(self):
        with self.assertRaisesRegex(RuntimeError, "rebuild"):
            plan_staging_files(
                available_file_ids=[1, 2],
                processed_file_ids=[1],
                stored_versions=["staging-v0"],
                rebuild=False,
            )

    def test_explicit_rebuild_processes_all_files(self):
        selected = plan_staging_files(
            available_file_ids=[1, 2],
            processed_file_ids=[1, 2],
            stored_versions=["staging-v0"],
            rebuild=True,
        )

        self.assertEqual(selected, [1, 2])

    def test_upsert_updates_only_when_incoming_version_is_newer(self):
        sql = build_staging_upsert_sql(UPSERT_TEST_COLUMNS)

        self.assertIn("ON CONFLICT", sql.upper())
        self.assertIn("DO UPDATE SET", sql.upper())
        self.assertIn("EXCLUDED.FECHA_EVENTO", sql.upper())
        self.assertIn("EXCLUDED.RAW_FILE_ID", sql.upper())
        self.assertIn("EXCLUDED.RAW_RECORD_ID", sql.upper())
        self.assertIn("TRANSFORMATION_VERSION", sql.upper())

    def test_schema_contract_supports_existing_volumes_and_fresh_init(self):
        root = Path(__file__).resolve().parents[1]
        schemas_sql = (root / "initdb" / "01_init_schemas.sql").read_text(encoding="utf-8")
        raw_sql = (root / "initdb" / "02_raw_tables.sql").read_text(encoding="utf-8")
        init_sql = (root / "initdb" / "03_staging_tables.sql").read_text(encoding="utf-8")
        migration_sql = (root / "sql" / "08_incremental_staging.sql").read_text(encoding="utf-8")

        for sql in (init_sql, migration_sql):
            self.assertIn("raw_record_id", sql)
            self.assertIn("transformation_version", sql)
            self.assertIn("processed_files", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS", migration_sql)
        self.assertIn("ALTER TABLE raw.raw_files", migration_sql)
        self.assertIn("ALTER TABLE raw.raw_records", migration_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS audit.pipeline_runs", schemas_sql)
        self.assertIn("run_id", raw_sql)


@unittest.skipUnless(
    os.getenv("ETL_POSTGRES_INTEGRATION") == "1",
    "Set ETL_POSTGRES_INTEGRATION=1 to use the existing PostgreSQL container.",
)
class IncrementalStagingPostgresTest(unittest.TestCase):
    def test_real_upsert_updates_newer_candidate_and_rolls_back(self):
        engine = create_engine(os.environ["DATABASE_URL"])
        connection = engine.connect()
        transaction = connection.begin()
        try:
            target = connection.execute(text("""
                SELECT fuente, plataforma, id_origen_registro, nombre_agente,
                       tipo_fuente, categoria
                FROM staging.stg_actividad_agente_ia
                ORDER BY id
                LIMIT 1
            """)).mappings().one()
            raw_ref = connection.execute(text("""
                SELECT id AS raw_record_id, file_id AS raw_file_id
                FROM raw.raw_records
                ORDER BY id DESC
                LIMIT 1
            """)).mappings().one()
            columns = [
                "fuente", "plataforma", "id_origen_registro", "nombre_agente",
                "tipo_fuente", "fecha_evento", "categoria", "titulo",
                "raw_file_id", "raw_record_id", "transformation_version",
            ]
            marker = "incremental-integration-probe"
            params = {
                **target,
                **raw_ref,
                "fecha_evento": "2099-01-01",
                "titulo": marker,
                "transformation_version": TRANSFORMATION_VERSION,
            }

            connection.execute(text(build_staging_upsert_sql(columns)), params)
            observed = connection.execute(text("""
                SELECT titulo
                FROM staging.stg_actividad_agente_ia
                WHERE fuente = :fuente
                  AND plataforma = :plataforma
                  AND id_origen_registro = :id_origen_registro
                  AND nombre_agente = :nombre_agente
            """), target).scalar_one()

            self.assertEqual(observed, marker)
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
