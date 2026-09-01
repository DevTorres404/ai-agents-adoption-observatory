-- Matrices Extendidas de Calidad de Datos (Entregable 3)

CREATE TABLE IF NOT EXISTS audit.quality_summary (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_raw_records INTEGER,
    eligible_records INTEGER,
    expected_staging_records INTEGER,
    total_staging_records INTEGER,
    load_error_records INTEGER,
    completion_rate NUMERIC(5,2),
    total_duplicates_removed INTEGER,
    deduplication_rate NUMERIC(5,2),
    total_nulls_removed INTEGER,
    overall_error_rate NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS audit.nulls_matrix (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
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
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(100),
    total_detected INTEGER,
    total_removed INTEGER,
    total_kept INTEGER
);

CREATE TABLE IF NOT EXISTS audit.casting_report (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
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
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
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

CREATE TABLE IF NOT EXISTS audit.source_freshness (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source VARCHAR(100) NOT NULL,
    latest_status VARCHAR(30) NOT NULL,
    records_extracted INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ NOT NULL,
    last_success_at TIMESTAMPTZ,
    age_hours NUMERIC(12,2),
    is_stale BOOLEAN NOT NULL,
    expected_queries INTEGER,
    completed_queries INTEGER,
    PRIMARY KEY(run_id, source)
);

CREATE TABLE IF NOT EXISTS audit.semantic_coverage (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source VARCHAR(100) NOT NULL,
    dimension VARCHAR(30) NOT NULL,
    total_count INTEGER NOT NULL,
    covered_count INTEGER NOT NULL,
    coverage_pct NUMERIC(5,2) NOT NULL,
    threshold_pct NUMERIC(5,2) NOT NULL,
    warning BOOLEAN NOT NULL,
    enforcement_mode VARCHAR(30) NOT NULL DEFAULT 'warning_only',
    PRIMARY KEY(run_id, source, dimension)
);

CREATE TABLE IF NOT EXISTS audit.quality_warnings (
    id BIGSERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source VARCHAR(100) NOT NULL,
    dimension VARCHAR(30) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, source, dimension)
);

CREATE TABLE IF NOT EXISTS audit.relevance_sample (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    sample_seed VARCHAR(255) NOT NULL,
    source VARCHAR(100) NOT NULL,
    agent VARCHAR(255) NOT NULL,
    raw_record_id BIGINT REFERENCES raw.raw_records(id),
    sample_key CHAR(64) NOT NULL,
    title TEXT,
    url TEXT,
    label VARCHAR(100),
    reviewer VARCHAR(255),
    reviewed_at TIMESTAMPTZ,
    PRIMARY KEY(run_id, sample_key)
);

CREATE TABLE IF NOT EXISTS audit.source_comparable_metrics (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source VARCHAR(100) NOT NULL,
    agent VARCHAR(255) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    raw_value NUMERIC,
    normalization_method VARCHAR(80) NOT NULL,
    normalized_value NUMERIC(12,6) NOT NULL,
    PRIMARY KEY(run_id, source, agent, metric_name)
);
