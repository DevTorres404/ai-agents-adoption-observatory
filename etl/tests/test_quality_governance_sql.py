import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

from src.quality.quality_checks import build_candidate_staging_frame, get_nulls_matrix, get_overall_metrics
from src.utils.db import db_connector


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "10_quality_governance.sql"
INITDB = ROOT / "initdb" / "05_audit_extended_tables.sql"


class QualityGovernanceSqlContractTest(unittest.TestCase):
    def test_all_quality_metrics_are_run_scoped(self):
        migration = MIGRATION.read_text(encoding="utf-8").lower()
        initdb = INITDB.read_text(encoding="utf-8").lower()
        for table in (
            "quality_summary", "nulls_matrix", "dedup_report", "casting_report",
            "quality_issue_breakdown", "source_freshness", "semantic_coverage",
            "quality_warnings", "relevance_sample", "source_comparable_metrics",
        ):
            self.assertIn(f"audit.{table}", migration)
            self.assertIn(f"audit.{table}", initdb)
        self.assertGreaterEqual(initdb.count("run_id integer not null references audit.pipeline_runs"), 10)
        self.assertIn("add column if not exists run_id", migration)

    def test_schema_keeps_manual_labels_and_source_local_normalization_explicit(self):
        schema = INITDB.read_text(encoding="utf-8").lower()
        self.assertIn("label varchar", schema)
        self.assertIn("reviewer varchar", schema)
        self.assertIn("reviewed_at timestamptz", schema)
        self.assertIn("normalization_method", schema)
        self.assertIn("expected_queries", schema)
        self.assertIn("completed_queries", schema)


@unittest.skipUnless(
    os.getenv("ETL_POSTGRES_INTEGRATION") == "1",
    "Set ETL_POSTGRES_INTEGRATION=1 for rollback-only PostgreSQL integration.",
)
class QualityGovernancePostgresTest(unittest.TestCase):
    def test_migration_twice_and_run_isolation(self):
        engine = create_engine(os.environ["DATABASE_URL"])
        migration = MIGRATION.read_text(encoding="utf-8")
        with engine.begin() as connection:
            connection.exec_driver_sql(migration)
            connection.exec_driver_sql(migration)

        connection = engine.connect()
        transaction = connection.begin()
        try:
            run_a = connection.execute(text(
                "INSERT INTO audit.pipeline_runs(status) VALUES ('running') RETURNING run_id"
            )).scalar_one()
            run_b = connection.execute(text(
                "INSERT INTO audit.pipeline_runs(status) VALUES ('running') RETURNING run_id"
            )).scalar_one()
            for run_id, raw_count in ((run_a, 3), (run_b, 5)):
                connection.execute(text("""
                    INSERT INTO audit.quality_summary
                    (run_id, total_raw_records, eligible_records, expected_staging_records,
                     total_staging_records, load_error_records, completion_rate,
                     total_duplicates_removed, deduplication_rate, total_nulls_removed, overall_error_rate)
                    VALUES (:run_id, :raw, :raw, :raw, :raw, 0, 100, 0, 0, 0, 0)
                """), {"run_id": run_id, "raw": raw_count})
            observed = connection.execute(text("""
                SELECT run_id, total_raw_records FROM audit.quality_summary
                WHERE run_id IN (:a, :b) ORDER BY run_id
            """), {"a": run_a, "b": run_b}).all()
            self.assertEqual(observed, [(run_a, 3), (run_b, 5)])
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()

    def test_run_scoped_quality_queries_use_one_snapshot(self):
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.begin() as migration_connection:
            migration_connection.exec_driver_sql(MIGRATION.read_text(encoding="utf-8"))

        connection = engine.connect()
        transaction = connection.begin()
        original_engine = db_connector.engine

        class _ConnectionContext:
            def __enter__(self):
                return connection

            def __exit__(self, *_args):
                return False

        class _EngineProxy:
            @staticmethod
            def connect():
                return _ConnectionContext()

        try:
            db_connector.engine = _EngineProxy()
            run_id = connection.execute(text(
                "INSERT INTO audit.pipeline_runs(status) VALUES ('running') RETURNING run_id"
            )).scalar_one()
            file_id = connection.execute(text("""
                INSERT INTO raw.raw_files
                (fuente, tipo_fuente, ruta_relativa, nombre_archivo, hash_sha256, run_id)
                VALUES ('github', 'api', :path, :name, :hash, :run_id) RETURNING id
            """), {
                "path": f"quality/{run_id}.json", "name": f"quality-{run_id}.json",
                "hash": f"quality-governance-{run_id}", "run_id": run_id,
            }).scalar_one()
            raw_record_id = connection.execute(text("""
                INSERT INTO raw.raw_records(file_id, raw_data, run_id)
                VALUES (:file_id, '{"id":"quality-probe","name":"Codex","description":"Codex"}'::jsonb, :run_id)
                RETURNING id
            """), {"file_id": file_id, "run_id": run_id}).scalar_one()
            connection.execute(text("""
                INSERT INTO staging.stg_actividad_agente_ia
                (id_origen_registro, fuente, tipo_fuente, plataforma, fecha_evento,
                 nombre_agente, categoria, dim_nombre_plataforma, dim_nombre_tecnologia,
                 dim_nombre_comunidad, raw_file_id, raw_record_id, transformation_version)
                VALUES ('quality-probe', 'github', 'api', 'github', DATE '2026-08-27',
                 'Codex', 'desarrollo', 'GitHub', 'Python', 'OpenAI', :file_id, :raw_record_id, 'staging-v1')
            """), {"file_id": file_id, "raw_record_id": raw_record_id})

            build_candidate_staging_frame.cache_clear()
            summary = get_overall_metrics(run_id)
            nulls = get_nulls_matrix(run_id)
            self.assertEqual(summary["total_raw_records"], 1)
            self.assertEqual(summary["total_staging_records"], 1)
            self.assertEqual(summary["overall_error_rate"], 0.0)
            self.assertTrue(all(row["total_count"] == 1 for row in nulls))
        finally:
            build_candidate_staging_frame.cache_clear()
            db_connector.engine = original_engine
            transaction.rollback()
            connection.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
