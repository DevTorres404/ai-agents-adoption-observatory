import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS_SQL = ROOT / "sql" / "02_load_gold_dimensions.sql"
FACT_SQL = ROOT / "sql" / "03_load_gold_fact.sql"
MIGRATION_SQL = ROOT / "sql" / "09_incremental_gold.sql"
GOLD_SCHEMA_SQL = ROOT / "initdb" / "01_create_gold_schema.sql"
PIPELINE_PY = ROOT / "src" / "scripts" / "run_pipeline.py"


class GoldIncrementalContractTest(unittest.TestCase):
    def test_normal_loaders_use_upserts_without_implicit_truncate(self):
        dimensions = DIMENSIONS_SQL.read_text(encoding="utf-8")
        fact = FACT_SQL.read_text(encoding="utf-8")

        self.assertNotIn("TRUNCATE TABLE", dimensions.upper())
        self.assertNotIn("TRUNCATE TABLE", fact.upper())
        self.assertGreaterEqual(dimensions.upper().count("ON CONFLICT"), 6)
        self.assertIn("DO UPDATE SET", fact.upper())

    def test_schema_and_migration_define_stable_fact_lineage(self):
        schema = GOLD_SCHEMA_SQL.read_text(encoding="utf-8")
        migration = MIGRATION_SQL.read_text(encoding="utf-8")

        for sql in (schema, migration):
            self.assertIn("raw_record_id", sql)
            self.assertIn("fact_lineage_key", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS", migration)
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS", migration)

    def test_rebuild_is_explicit_and_default_remains_incremental(self):
        pipeline = PIPELINE_PY.read_text(encoding="utf-8")

        self.assertIn('"--gold-mode"', pipeline)
        self.assertIn('default="incremental"', pipeline)
        self.assertIn('args.gold_mode == "rebuild"', pipeline)


@unittest.skipUnless(
    os.getenv("ETL_POSTGRES_INTEGRATION") == "1",
    "Set ETL_POSTGRES_INTEGRATION=1 with an isolated PostgreSQL database.",
)
class GoldIncrementalPostgresTest(unittest.TestCase):
    def test_rerun_preserves_keys_updates_attributes_and_never_deletes_absent_rows(self):
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.begin() as connection:
            migration = MIGRATION_SQL.read_text(encoding="utf-8")
            connection.exec_driver_sql(migration)
            connection.exec_driver_sql(migration)
            raw_record_fks = connection.execute(text("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conrelid = 'gold.fact_actividad_agente_ia'::regclass
                  AND contype = 'f'
                  AND conkey = ARRAY[(
                      SELECT attnum
                      FROM pg_attribute
                      WHERE attrelid = 'gold.fact_actividad_agente_ia'::regclass
                        AND attname = 'raw_record_id'
                  )]::smallint[]
            """)).scalar_one()
            self.assertEqual(raw_record_fks, 1)

        connection = engine.connect()
        transaction = connection.begin()
        try:
            connection.execute(text("""
                INSERT INTO audit.pipeline_runs (status) VALUES ('running')
            """))
            run_id = connection.execute(text("""
                SELECT MAX(run_id) FROM audit.pipeline_runs
            """)).scalar_one()
            file_id = connection.execute(text("""
                INSERT INTO raw.raw_files (
                    fuente, tipo_fuente, ruta_relativa, nombre_archivo,
                    hash_sha256, run_id
                ) VALUES (
                    'gold_probe', 'api', 'probe.json', 'probe.json',
                    'gold-incremental-probe', :run_id
                ) RETURNING id
            """), {"run_id": run_id}).scalar_one()
            raw_record_id = connection.execute(text("""
                INSERT INTO raw.raw_records (file_id, raw_data, run_id)
                VALUES (:file_id, '{}'::jsonb, :run_id)
                RETURNING id
            """), {"file_id": file_id, "run_id": run_id}).scalar_one()
            connection.execute(text("""
                INSERT INTO staging.stg_actividad_agente_ia (
                    id_origen_registro, fuente, tipo_fuente, plataforma,
                    fecha_evento, nombre_agente, categoria, titulo,
                    cantidad_menciones, cantidad_interacciones,
                    dim_nombre_plataforma, dim_tipo_plataforma, dim_ecosistema,
                    dim_nombre_tecnologia, dim_categoria_tecnologia,
                    dim_dominio_tecnologico, dim_tipo_senal,
                    dim_nombre_comunidad, dim_tipo_comunidad,
                    dim_region_comunidad, raw_file_id, raw_record_id,
                    transformation_version
                ) VALUES (
                    'repo-1', 'gold_probe', 'api', 'gold_probe', DATE '2026-01-01',
                    'Gold Probe Agent', 'desarrollo', 'first title', 1, 2,
                    'Gold Probe Platform', 'repositorio', 'Gold Probe Ecosystem', 'Gold Probe Technology', 'lenguaje',
                    'software', 'actividad técnica', 'Gold Probe Community', 'organización',
                    'Global', :file_id, :raw_record_id, 'staging-v1'
                )
            """), {"file_id": file_id, "raw_record_id": raw_record_id})

            dimensions_sql = DIMENSIONS_SQL.read_text(encoding="utf-8")
            fact_sql = FACT_SQL.read_text(encoding="utf-8")
            connection.exec_driver_sql(dimensions_sql)
            connection.exec_driver_sql(fact_sql)
            first = connection.execute(text("""
                SELECT f.id_fact_actividad, f.fact_lineage_key, f.raw_record_id,
                       f.titulo,
                       da.id_agente, df.id_fuente, dp.id_plataforma,
                       dtec.id_tecnologia, dc.id_comunidad
                FROM gold.fact_actividad_agente_ia f
                JOIN gold.dim_agente da ON da.id_agente = f.id_agente
                JOIN gold.dim_fuente df ON df.id_fuente = f.id_fuente
                JOIN gold.dim_plataforma dp ON dp.id_plataforma = f.id_plataforma
                JOIN gold.dim_tecnologia dtec ON dtec.id_tecnologia = f.id_tecnologia
                JOIN gold.dim_comunidad dc ON dc.id_comunidad = f.id_comunidad
                WHERE f.fact_lineage_key = :lineage
            """), {"lineage": f"raw:{raw_record_id}"}).mappings().one()

            next_raw_record_id = connection.execute(text("""
                INSERT INTO raw.raw_records (file_id, raw_data, run_id)
                VALUES (:file_id, '{"version": 2}'::jsonb, :run_id)
                RETURNING id
            """), {"file_id": file_id, "run_id": run_id}).scalar_one()
            connection.execute(text("""
                UPDATE staging.stg_actividad_agente_ia
                SET titulo = 'updated title', cantidad_interacciones = 9,
                    raw_record_id = :raw_record_id,
                    dim_ecosistema = 'Updated ecosystem'
                WHERE id_origen_registro = 'repo-1'
            """), {"raw_record_id": next_raw_record_id})
            connection.exec_driver_sql(dimensions_sql)
            connection.exec_driver_sql(fact_sql)
            second = connection.execute(text("""
                SELECT id_fact_actividad, fact_lineage_key, raw_record_id, titulo,
                       id_agente, id_fuente, id_plataforma, id_tecnologia, id_comunidad
                FROM gold.fact_actividad_agente_ia
                WHERE fact_lineage_key = :lineage
            """), {"lineage": first["fact_lineage_key"]}).mappings().one()

            self.assertEqual(second["id_fact_actividad"], first["id_fact_actividad"])
            self.assertEqual(second["fact_lineage_key"], first["fact_lineage_key"])
            self.assertEqual(first["fact_lineage_key"], f"raw:{raw_record_id}")
            self.assertEqual(second["raw_record_id"], next_raw_record_id)
            self.assertEqual(second["titulo"], "updated title")
            for key in ("id_agente", "id_fuente", "id_plataforma", "id_tecnologia", "id_comunidad"):
                self.assertEqual(second[key], first[key])
            self.assertEqual(
                connection.execute(text("""
                    SELECT ecosistema
                    FROM gold.dim_plataforma
                    WHERE id_plataforma = :id_plataforma
                """), {"id_plataforma": first["id_plataforma"]}).scalar_one(),
                "Updated ecosystem",
            )
            self.assertEqual(connection.execute(text("""
                SELECT COUNT(*) FROM gold.fact_actividad_agente_ia
                WHERE fact_lineage_key = :lineage
            """), {"lineage": first["fact_lineage_key"]}).scalar_one(), 1)
            connection.execute(text("DELETE FROM staging.stg_actividad_agente_ia"))
            connection.exec_driver_sql(dimensions_sql)
            connection.exec_driver_sql(fact_sql)
            self.assertEqual(connection.execute(text("""
                SELECT COUNT(*) FROM gold.fact_actividad_agente_ia
                WHERE fact_lineage_key = :lineage
            """), {"lineage": first["fact_lineage_key"]}).scalar_one(), 1)
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
