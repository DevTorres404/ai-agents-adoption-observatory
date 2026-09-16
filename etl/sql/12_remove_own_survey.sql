-- User-authorized retirement of the own-survey source.
-- Stop old workers first. Requires the current Raw/Staging/Gold/governance schemas.
-- Idempotent, transactional, and never deletes another source's observations.
BEGIN;
SET LOCAL lock_timeout = '30s';
SELECT pg_advisory_xact_lock(719260916);

CREATE TEMP TABLE retired_survey_files ON COMMIT DROP AS
SELECT id, run_id FROM raw.raw_files WHERE fuente IN ('fuente_propia', 'encuesta');
CREATE TEMP TABLE retired_survey_records ON COMMIT DROP AS
SELECT id, run_id FROM raw.raw_records
WHERE file_id IN (SELECT id FROM retired_survey_files);
CREATE TEMP TABLE retired_survey_runs ON COMMIT DROP AS
SELECT run_id FROM retired_survey_files WHERE run_id IS NOT NULL
UNION SELECT run_id FROM retired_survey_records WHERE run_id IS NOT NULL
UNION SELECT run_id FROM staging.processed_files
      WHERE file_id IN (SELECT id FROM retired_survey_files) AND run_id IS NOT NULL
UNION SELECT run_id FROM audit.source_freshness WHERE source IN ('fuente_propia', 'encuesta')
UNION SELECT run_id FROM audit.relevance_sample WHERE source IN ('fuente_propia', 'encuesta')
UNION SELECT run_id FROM audit.source_comparable_metrics WHERE source IN ('fuente_propia', 'encuesta');

-- Re-audits of the removed cohorts are invalid too; do not keep stale totals.
INSERT INTO retired_survey_runs
SELECT DISTINCT run_id FROM audit.quality_summary
WHERE data_run_id IN (SELECT run_id FROM retired_survey_runs)
  AND run_id NOT IN (SELECT run_id FROM retired_survey_runs);

-- Remove children before their Raw lineage (no CASCADE across unrelated data).
DELETE FROM gold.fact_actividad_agente_ia
WHERE id_fuente IN (SELECT id_fuente FROM gold.dim_fuente WHERE nombre_fuente IN ('fuente_propia', 'encuesta'))
   OR raw_file_id IN (SELECT id FROM retired_survey_files)
   OR raw_record_id IN (SELECT id FROM retired_survey_records);

DELETE FROM audit.relevance_sample
WHERE source IN ('fuente_propia', 'encuesta')
   OR raw_record_id IN (SELECT id FROM retired_survey_records);
DELETE FROM staging.stg_actividad_agente_ia
WHERE fuente IN ('fuente_propia', 'encuesta') OR plataforma = 'encuesta_upse'
   OR raw_file_id IN (SELECT id FROM retired_survey_files)
   OR raw_record_id IN (SELECT id FROM retired_survey_records);
DELETE FROM staging.processed_files WHERE file_id IN (SELECT id FROM retired_survey_files);
DELETE FROM raw.raw_records WHERE id IN (SELECT id FROM retired_survey_records);
DELETE FROM raw.raw_files WHERE id IN (SELECT id FROM retired_survey_files);

DELETE FROM gold.dim_fuente WHERE nombre_fuente IN ('fuente_propia', 'encuesta');
DELETE FROM gold.dim_comunidad d
WHERE d.nombre_comunidad = 'Comunidad UPSE'
  AND NOT EXISTS (SELECT 1 FROM gold.fact_actividad_agente_ia f WHERE f.id_comunidad = d.id_comunidad)
  AND NOT EXISTS (SELECT 1 FROM staging.stg_actividad_agente_ia s WHERE s.dim_nombre_comunidad = d.nombre_comunidad);
DELETE FROM gold.dim_plataforma d
WHERE d.nombre_plataforma = 'encuesta_upse'
  AND NOT EXISTS (SELECT 1 FROM gold.fact_actividad_agente_ia f WHERE f.id_plataforma = d.id_plataforma)
  AND NOT EXISTS (SELECT 1 FROM staging.stg_actividad_agente_ia s WHERE s.dim_nombre_plataforma = d.nombre_plataforma);

DELETE FROM audit.nulls_matrix WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.dedup_report WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.casting_report WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.homologation_map WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.source_freshness WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.semantic_coverage WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.quality_warnings WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.source_comparable_metrics WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.pipeline_errors WHERE source IN ('fuente_propia', 'encuesta');
DELETE FROM audit.quality_issue_breakdown
WHERE metric_name = 'google_forms_survey_records'
   OR run_id IN (SELECT run_id FROM retired_survey_runs);
DELETE FROM audit.quality_summary WHERE run_id IN (SELECT run_id FROM retired_survey_runs);

-- Retain run identity for the other sources, but never present obsolete totals.
UPDATE audit.pipeline_runs SET
    status = 'invalidated_source_removal',
    error_message = 'Retired source removed; rerun quality for the remaining data.',
    total_raw_records = NULL, total_staging_records = NULL,
    records_discarded = NULL, completion_rate = NULL
WHERE run_id IN (SELECT run_id FROM retired_survey_runs);

ALTER TABLE gold.dim_fuente DROP COLUMN IF EXISTS es_fuente_propia;
COMMIT;
