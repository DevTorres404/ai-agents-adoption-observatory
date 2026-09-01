-- Idempotent run-scoped quality governance migration for existing volumes.
BEGIN;

ALTER TABLE audit.quality_summary ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE audit.quality_summary ADD COLUMN IF NOT EXISTS eligible_records INTEGER;
ALTER TABLE audit.quality_summary ADD COLUMN IF NOT EXISTS expected_staging_records INTEGER;
ALTER TABLE audit.quality_summary ADD COLUMN IF NOT EXISTS load_error_records INTEGER;
ALTER TABLE audit.quality_summary ADD COLUMN IF NOT EXISTS deduplication_rate NUMERIC(5,2);
ALTER TABLE audit.nulls_matrix ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE audit.dedup_report ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE audit.casting_report ADD COLUMN IF NOT EXISTS run_id INTEGER;
ALTER TABLE audit.quality_issue_breakdown ADD COLUMN IF NOT EXISTS run_id INTEGER;

DO $$
DECLARE legacy_run_id INTEGER;
BEGIN
    IF EXISTS (SELECT 1 FROM audit.quality_summary WHERE run_id IS NULL)
       OR EXISTS (SELECT 1 FROM audit.nulls_matrix WHERE run_id IS NULL)
       OR EXISTS (SELECT 1 FROM audit.dedup_report WHERE run_id IS NULL)
       OR EXISTS (SELECT 1 FROM audit.casting_report WHERE run_id IS NULL)
       OR EXISTS (SELECT 1 FROM audit.quality_issue_breakdown WHERE run_id IS NULL) THEN
        INSERT INTO audit.pipeline_runs (execution_end, status, error_message)
        VALUES (CURRENT_TIMESTAMP, 'legacy_quality_backfill', 'Migrated pre-run-scoped quality evidence')
        RETURNING run_id INTO legacy_run_id;
        UPDATE audit.quality_summary SET run_id = legacy_run_id WHERE run_id IS NULL;
        UPDATE audit.nulls_matrix SET run_id = legacy_run_id WHERE run_id IS NULL;
        UPDATE audit.dedup_report SET run_id = legacy_run_id WHERE run_id IS NULL;
        UPDATE audit.casting_report SET run_id = legacy_run_id WHERE run_id IS NULL;
        UPDATE audit.quality_issue_breakdown SET run_id = legacy_run_id WHERE run_id IS NULL;
    END IF;
END $$;

ALTER TABLE audit.quality_summary ALTER COLUMN run_id SET NOT NULL;
ALTER TABLE audit.nulls_matrix ALTER COLUMN run_id SET NOT NULL;
ALTER TABLE audit.dedup_report ALTER COLUMN run_id SET NOT NULL;
ALTER TABLE audit.casting_report ALTER COLUMN run_id SET NOT NULL;
ALTER TABLE audit.quality_issue_breakdown ALTER COLUMN run_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'quality_summary_run_fk') THEN
        ALTER TABLE audit.quality_summary ADD CONSTRAINT quality_summary_run_fk FOREIGN KEY (run_id) REFERENCES audit.pipeline_runs(run_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'nulls_matrix_run_fk') THEN
        ALTER TABLE audit.nulls_matrix ADD CONSTRAINT nulls_matrix_run_fk FOREIGN KEY (run_id) REFERENCES audit.pipeline_runs(run_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'dedup_report_run_fk') THEN
        ALTER TABLE audit.dedup_report ADD CONSTRAINT dedup_report_run_fk FOREIGN KEY (run_id) REFERENCES audit.pipeline_runs(run_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'casting_report_run_fk') THEN
        ALTER TABLE audit.casting_report ADD CONSTRAINT casting_report_run_fk FOREIGN KEY (run_id) REFERENCES audit.pipeline_runs(run_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'quality_issue_breakdown_run_fk') THEN
        ALTER TABLE audit.quality_issue_breakdown ADD CONSTRAINT quality_issue_breakdown_run_fk FOREIGN KEY (run_id) REFERENCES audit.pipeline_runs(run_id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS audit.source_freshness (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id), source VARCHAR(100) NOT NULL,
    latest_status VARCHAR(30) NOT NULL, records_extracted INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ NOT NULL, last_success_at TIMESTAMPTZ, age_hours NUMERIC(12,2),
    is_stale BOOLEAN NOT NULL, expected_queries INTEGER, completed_queries INTEGER,
    PRIMARY KEY(run_id, source)
);
CREATE TABLE IF NOT EXISTS audit.semantic_coverage (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id), source VARCHAR(100) NOT NULL,
    dimension VARCHAR(30) NOT NULL, total_count INTEGER NOT NULL, covered_count INTEGER NOT NULL,
    coverage_pct NUMERIC(5,2) NOT NULL, threshold_pct NUMERIC(5,2) NOT NULL,
    warning BOOLEAN NOT NULL, enforcement_mode VARCHAR(30) NOT NULL DEFAULT 'warning_only',
    PRIMARY KEY(run_id, source, dimension)
);
CREATE TABLE IF NOT EXISTS audit.quality_warnings (
    id BIGSERIAL PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source VARCHAR(100) NOT NULL, dimension VARCHAR(30) NOT NULL, message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(run_id, source, dimension)
);
CREATE TABLE IF NOT EXISTS audit.relevance_sample (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id), sample_seed VARCHAR(255) NOT NULL,
    source VARCHAR(100) NOT NULL, agent VARCHAR(255) NOT NULL,
    raw_record_id BIGINT REFERENCES raw.raw_records(id), sample_key CHAR(64) NOT NULL,
    title TEXT, url TEXT, label VARCHAR(100), reviewer VARCHAR(255), reviewed_at TIMESTAMPTZ,
    PRIMARY KEY(run_id, sample_key)
);
CREATE TABLE IF NOT EXISTS audit.source_comparable_metrics (
    run_id INTEGER NOT NULL REFERENCES audit.pipeline_runs(run_id), source VARCHAR(100) NOT NULL,
    agent VARCHAR(255) NOT NULL, metric_name VARCHAR(100) NOT NULL, raw_value NUMERIC,
    normalization_method VARCHAR(80) NOT NULL, normalized_value NUMERIC(12,6) NOT NULL,
    PRIMARY KEY(run_id, source, agent, metric_name)
);

COMMIT;
