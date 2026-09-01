-- Idempotent migration for databases whose PostgreSQL volume already exists.

ALTER TABLE raw.raw_files
    ADD COLUMN IF NOT EXISTS run_id INTEGER REFERENCES audit.pipeline_runs(run_id);

ALTER TABLE raw.raw_records
    ADD COLUMN IF NOT EXISTS run_id INTEGER REFERENCES audit.pipeline_runs(run_id);

ALTER TABLE staging.stg_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS raw_record_id INTEGER REFERENCES raw.raw_records(id);

ALTER TABLE staging.stg_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS transformation_version VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS ux_staging_activity_business_key
    ON staging.stg_actividad_agente_ia
       (fuente, plataforma, id_origen_registro, nombre_agente);

CREATE TABLE IF NOT EXISTS staging.processed_files (
    file_id INTEGER PRIMARY KEY REFERENCES raw.raw_files(id) ON DELETE CASCADE,
    transformation_version VARCHAR(50) NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id INTEGER REFERENCES audit.pipeline_runs(run_id),
    records_processed INTEGER NOT NULL DEFAULT 0
);
