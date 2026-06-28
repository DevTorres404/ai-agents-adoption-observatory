-- Matrices Extendidas de Calidad de Datos (Entregable 3)

CREATE TABLE IF NOT EXISTS audit.quality_summary (
    id SERIAL PRIMARY KEY,
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_raw_records INTEGER,
    total_staging_records INTEGER,
    completion_rate NUMERIC(5,2),
    total_duplicates_removed INTEGER,
    total_nulls_removed INTEGER,
    overall_error_rate NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS audit.nulls_matrix (
    id SERIAL PRIMARY KEY,
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    column_name VARCHAR(100),
    null_count INTEGER,
    total_count INTEGER,
    null_percentage NUMERIC(5,2),
    strategy_applied VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS audit.dedup_report (
    id SERIAL PRIMARY KEY,
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    total_detected INTEGER,
    total_removed INTEGER,
    total_kept INTEGER
);

CREATE TABLE IF NOT EXISTS audit.casting_report (
    id SERIAL PRIMARY KEY,
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    field_name VARCHAR(100),
    target_type VARCHAR(50),
    failed_conversions INTEGER,
    example_before TEXT,
    example_after TEXT
);

CREATE TABLE IF NOT EXISTS audit.quality_issue_breakdown (
    id SERIAL PRIMARY KEY,
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metric_name VARCHAR(120),
    metric_value INTEGER,
    evidence_basis TEXT,
    academic_interpretation TEXT
);

CREATE TABLE IF NOT EXISTS audit.homologation_map (
    id SERIAL PRIMARY KEY,
    source VARCHAR(100),
    source_field VARCHAR(100),
    staging_field VARCHAR(100),
    transformation_rule TEXT,
    UNIQUE(source, source_field, staging_field)
);
