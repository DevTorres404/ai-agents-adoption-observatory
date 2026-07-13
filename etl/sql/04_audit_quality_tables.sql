-- Tablas de Auditoría y Calidad (Entregable 3/4)

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

CREATE TABLE IF NOT EXISTS audit.pipeline_errors (
    error_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES audit.pipeline_runs(run_id),
    error_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    error_type VARCHAR(100),
    description TEXT,
    action_taken VARCHAR(255)
);
