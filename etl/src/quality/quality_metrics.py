import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from src.quality.governance import (
    build_source_freshness,
    build_source_metrics,
    build_stratified_sample,
    calculate_semantic_coverage,
    publish_quality_evidence,
)
from src.quality.quality_checks import (
    build_candidate_staging_frame,
    get_casting_report,
    get_dedup_report,
    get_homologation_map,
    get_nulls_matrix,
    get_overall_metrics,
    get_staging_contract_report,
)
from src.utils.db import db_connector
from src.utils.extraction_evidence import ExtractionStatus
from src.utils.logger import global_logger
from src.utils.paths import ROOT_DIR


QUALITY_TABLES = (
    "quality_summary", "nulls_matrix", "dedup_report", "casting_report",
    "quality_issue_breakdown", "source_freshness", "semantic_coverage",
    "quality_warnings", "relevance_sample", "source_comparable_metrics",
)


def _thresholds():
    defaults = {"platform": "80", "technology": "70", "community": "60", "llm": "50"}
    return {
        name: float(os.getenv(f"QUALITY_COVERAGE_{name.upper()}_PCT", default))
        for name, default in defaults.items()
    }


def _staging_snapshot(conn, run_id):
    return pd.read_sql(text("""
        SELECT s.* FROM staging.stg_actividad_agente_ia s
        JOIN raw.raw_files f ON f.id = s.raw_file_id
        WHERE f.run_id = :run_id
    """), conn, params={"run_id": run_id})


def _previous_success(conn):
    rows = conn.execute(text("""
        SELECT source, MAX(last_success_at) AS last_success_at
        FROM audit.source_freshness WHERE last_success_at IS NOT NULL GROUP BY source
    """)).mappings()
    return {row["source"]: row["last_success_at"] for row in rows}


def _latest_freshness(conn):
    rows = conn.execute(text("""
        SELECT DISTINCT ON (source)
               source, latest_status, records_extracted, last_attempt_at,
               last_success_at, expected_queries, completed_queries
        FROM audit.source_freshness
        ORDER BY source, run_id DESC
    """)).mappings()
    return {row["source"]: dict(row) for row in rows}


def _complete_freshness_snapshot(run_id, current_rows, previous_rows, now, stale_after_hours):
    rows_by_source = {row["source"]: row for row in current_rows}
    for source, previous in previous_rows.items():
        if source in rows_by_source:
            continue
        last_success = previous["last_success_at"]
        age = None if last_success is None else round(max((now - last_success).total_seconds(), 0) / 3600, 2)
        rows_by_source[source] = {
            "run_id": run_id,
            "source": source,
            "latest_status": previous["latest_status"],
            "records_extracted": previous["records_extracted"],
            "last_attempt_at": previous["last_attempt_at"],
            "last_success_at": last_success,
            "age_hours": age,
            "is_stale": last_success is None or age > stale_after_hours,
            "expected_queries": previous["expected_queries"],
            "completed_queries": previous["completed_queries"],
        }
    return [rows_by_source[source] for source in sorted(rows_by_source)]


def _issue_breakdown(run_id, summary, candidate):
    unmapped = int((candidate.get("nombre_agente", pd.Series(dtype=str)) == "Otro Agente IA").sum())
    values = [
        ("raw_records", summary["total_raw_records"], "Raw rows for this run.", "Run-scoped extraction denominator."),
        ("eligible_records", summary["eligible_records"], "Candidates matching an explicitly supported agent.", "Eligible denominator before deduplication."),
        ("historical_duplicates_removed", summary["total_duplicates_removed"], "Shared deterministic Staging deduplication rule.", "Intentional consolidation; not an ETL error."),
        ("expected_staging_records", summary["expected_staging_records"], "eligible_records - historical_duplicates_removed.", "Completion/error denominator."),
        ("materialized_staging_records", summary["total_staging_records"], "Staging rows whose Raw file belongs to this run.", "Materialized numerator."),
        ("load_error_records", summary["load_error_records"], "MAX(expected - materialized, 0).", "Unexplained loss; excludes deduplication."),
        ("unmapped_agent_records", unmapped, "Candidate rows classified as Otro Agente IA.", "Out-of-scope noise, separate from errors."),
    ]
    return [
        {"run_id": run_id, "metric_name": name, "metric_value": value,
         "evidence_basis": basis, "academic_interpretation": interpretation}
        for name, value, basis, interpretation in values
    ]


def _persist(conn, run_id, datasets):
    for table in QUALITY_TABLES:
        conn.execute(text(f"DELETE FROM audit.{table} WHERE run_id = :run_id"), {"run_id": run_id})

    conn.execute(text("""
        INSERT INTO audit.quality_summary
        (run_id, total_raw_records, eligible_records, expected_staging_records,
         total_staging_records, load_error_records, completion_rate,
         total_duplicates_removed, deduplication_rate, total_nulls_removed, overall_error_rate)
        VALUES (:run_id, :total_raw_records, :eligible_records, :expected_staging_records,
         :total_staging_records, :load_error_records, :completion_rate,
         :total_duplicates_removed, :deduplication_rate, :total_nulls_removed, :overall_error_rate)
    """), datasets["quality_summary"][0])

    statements = {
        "nulls_matrix": """INSERT INTO audit.nulls_matrix
            (run_id, source, column_name, null_count, total_count, null_percentage, strategy_applied)
            VALUES (:run_id, :source, :column_name, :null_count, :total_count, :null_percentage, :strategy_applied)""",
        "dedup_report": """INSERT INTO audit.dedup_report
            (run_id, source, total_detected, total_removed, total_kept)
            VALUES (:run_id, :source, :total_detected, :total_removed, :total_kept)""",
        "casting_report": """INSERT INTO audit.casting_report
            (run_id, source, field_name, target_type, failed_conversions, example_before, example_after)
            VALUES (:run_id, :source, :field_name, :target_type, :failed_conversions, :example_before, :example_after)""",
        "quality_issue_breakdown": """INSERT INTO audit.quality_issue_breakdown
            (run_id, metric_name, metric_value, evidence_basis, academic_interpretation)
            VALUES (:run_id, :metric_name, :metric_value, :evidence_basis, :academic_interpretation)""",
        "source_freshness": """INSERT INTO audit.source_freshness
            (run_id, source, latest_status, records_extracted, last_attempt_at, last_success_at,
             age_hours, is_stale, expected_queries, completed_queries)
            VALUES (:run_id, :source, :latest_status, :records_extracted, :last_attempt_at, :last_success_at,
             :age_hours, :is_stale, :expected_queries, :completed_queries)""",
        "semantic_coverage": """INSERT INTO audit.semantic_coverage
            (run_id, source, dimension, total_count, covered_count, coverage_pct, threshold_pct, warning, enforcement_mode)
            VALUES (:run_id, :source, :dimension, :total_count, :covered_count, :coverage_pct, :threshold_pct, :warning, :enforcement_mode)""",
        "quality_warnings": """INSERT INTO audit.quality_warnings (run_id, source, dimension, message)
            VALUES (:run_id, :source, :dimension, :message)""",
        "relevance_sample": """INSERT INTO audit.relevance_sample
            (run_id, sample_seed, source, agent, raw_record_id, sample_key, title, url, label, reviewer, reviewed_at)
            VALUES (:run_id, :sample_seed, :source, :agent, :raw_record_id, :sample_key, :title, :url, :label, :reviewer, :reviewed_at)""",
        "source_comparable_metrics": """INSERT INTO audit.source_comparable_metrics
            (run_id, source, agent, metric_name, raw_value, normalization_method, normalized_value)
            VALUES (:run_id, :source, :agent, :metric_name, :raw_value, :normalization_method, :normalized_value)""",
    }
    for name, statement in statements.items():
        if datasets[name]:
            conn.execute(text(statement), datasets[name])

    for item in datasets["homologation_map"]:
        conn.execute(text("""
            INSERT INTO audit.homologation_map (source, source_field, staging_field, transformation_rule)
            VALUES (:source, :source_field, :staging_field, :transformation_rule)
            ON CONFLICT (source, source_field, staging_field) DO NOTHING
        """), item)


def run_quality_framework(run_id=None, source_results=None, publication_status=ExtractionStatus.SUCCESS):
    """Persist and publish a coherent snapshot for exactly one pipeline run."""
    if not db_connector.engine:
        raise RuntimeError("Database connection is required for quality governance")
    if run_id is None:
        with db_connector.engine.begin() as conn:
            run_id = conn.execute(text(
                "INSERT INTO audit.pipeline_runs(status) VALUES ('running') RETURNING run_id"
            )).scalar_one()

    build_candidate_staging_frame.cache_clear()
    candidate = build_candidate_staging_frame(run_id)
    summary = get_overall_metrics(run_id)
    nulls = [{"run_id": run_id, **row} for row in get_nulls_matrix(run_id)]
    dedup = [{"run_id": run_id, **row} for row in get_dedup_report(run_id)]
    casting = [{"run_id": run_id, **row} for row in get_casting_report(run_id)]

    with db_connector.engine.begin() as conn:
        staging = _staging_snapshot(conn, run_id)
        now = datetime.now(timezone.utc)
        stale_after_hours = float(os.getenv("QUALITY_STALE_AFTER_HOURS", "24"))
        freshness = build_source_freshness(
            run_id, source_results or [], _previous_success(conn),
            now=now, stale_after_hours=stale_after_hours,
        )
        freshness = _complete_freshness_snapshot(
            run_id, freshness, _latest_freshness(conn), now, stale_after_hours
        )
        coverage = calculate_semantic_coverage(staging, run_id, _thresholds())
        warnings = [
            {"run_id": run_id, "source": row["source"], "dimension": row["dimension"],
             "message": f"Coverage {row['coverage_pct']}% is below warning threshold {row['threshold_pct']}%."}
            for row in coverage if row["warning"]
        ]
        sample = build_stratified_sample(
            staging, run_id, os.getenv("QUALITY_SAMPLE_SEED", "quality-v1"),
            int(os.getenv("QUALITY_SAMPLE_PER_STRATUM", "3")),
        )
        comparable = build_source_metrics(staging, run_id)
        datasets = {
            "quality_summary": [{"run_id": run_id, **summary}],
            "nulls_matrix": nulls,
            "dedup_report": dedup,
            "casting_report": casting,
            "quality_issue_breakdown": _issue_breakdown(run_id, summary, candidate),
            "source_freshness": freshness,
            "semantic_coverage": coverage,
            "quality_warnings": warnings,
            "relevance_sample": sample,
            "source_comparable_metrics": comparable,
            "homologation_map": get_homologation_map(),
            "staging_contract_columns": get_staging_contract_report(),
        }
        _persist(conn, run_id, datasets)

    frames = {name: pd.DataFrame(rows) for name, rows in datasets.items()}
    publish_quality_evidence(
        run_id, frames, publication_status,
        ROOT_DIR / "docs" / "evidencias" / "runs",
        ROOT_DIR / "docs" / "evidencias",
    )
    global_logger.info(f"Quality governance persisted and atomically published for run_id={run_id}")
    return datasets


if __name__ == "__main__":
    run_quality_framework()
