-- Creación de esquemas base
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS gold;

-- Raw and Staging reference a pipeline run before the later audit scripts run.
-- Define the shared parent table here so a fresh initdb execution is ordered.
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    execution_start TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    execution_end TIMESTAMP,
    total_raw_records INTEGER DEFAULT 0,
    total_staging_records INTEGER DEFAULT 0,
    records_discarded INTEGER DEFAULT 0,
    completion_rate NUMERIC(5,2),
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    error_message TEXT
);
