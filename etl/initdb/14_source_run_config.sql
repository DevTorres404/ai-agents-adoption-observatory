-- Additive migration: preserve historical runs and data.
ALTER TABLE audit.pipeline_runs
    ADD COLUMN IF NOT EXISTS run_config JSONB NOT NULL DEFAULT '{}'::JSONB;
COMMENT ON COLUMN audit.pipeline_runs.run_config IS
    'Requested source, date window, scope version, phase and parent data run; not a coverage guarantee.';
