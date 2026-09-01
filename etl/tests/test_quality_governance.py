from datetime import datetime, timezone

import pandas as pd

from src.quality.governance import (
    build_source_freshness,
    build_source_metrics,
    build_stratified_sample,
    calculate_semantic_coverage,
    publish_quality_evidence,
    reconcile_quality_counts,
)
from src.utils.extraction_evidence import ExtractionResult, ExtractionStatus
from src.utils.extraction_evidence import EvidenceRun


def test_reconciliation_keeps_deduplication_out_of_error_rate():
    result = reconcile_quality_counts(
        raw_records=10,
        eligible_records=8,
        duplicates_removed=2,
        materialized_records=5,
    )

    assert result["expected_staging_records"] == 6
    assert result["load_error_records"] == 1
    assert result["completion_rate"] == 83.33
    assert result["overall_error_rate"] == 16.67
    assert result["deduplication_rate"] == 25.0


def test_google_trends_empty_success_is_fresh_not_failed():
    now = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    rows = build_source_freshness(
        run_id=7,
        results=[
            ExtractionResult(
                source="google_trends",
                status=ExtractionStatus.EMPTY,
                records_extracted=0,
                query="Cursor",
                execution_timestamp=now.isoformat(),
            )
        ],
        previous_success={},
        now=now,
        stale_after_hours=24,
    )

    assert rows == [{
        "run_id": 7,
        "source": "google_trends",
        "latest_status": "empty",
        "records_extracted": 0,
        "last_attempt_at": now,
        "last_success_at": now,
        "age_hours": 0.0,
        "is_stale": False,
        "expected_queries": 1,
        "completed_queries": 1,
    }]


def test_coverage_warnings_are_configurable_and_zero_rows_are_not_warned():
    frame = pd.DataFrame([
        {"fuente": "github", "dim_nombre_plataforma": "GitHub", "dim_nombre_tecnologia": "Python", "dim_nombre_comunidad": "org", "llm_confianza": 0.8},
        {"fuente": "github", "dim_nombre_plataforma": "N/A", "dim_nombre_tecnologia": None, "dim_nombre_comunidad": "", "llm_confianza": 0.0},
    ])
    rows = calculate_semantic_coverage(
        frame,
        run_id=7,
        thresholds={"platform": 60, "technology": 40, "community": 40, "llm": 60},
    )
    by_dimension = {row["dimension"]: row for row in rows}

    assert by_dimension["platform"]["coverage_pct"] == 50.0
    assert by_dimension["platform"]["warning"] is True
    assert by_dimension["technology"]["warning"] is False
    assert by_dimension["llm"]["warning"] is True


def test_sample_is_stratified_reproducible_and_unlabelled():
    frame = pd.DataFrame([
        {"raw_record_id": n, "fuente": "github", "nombre_agente": agent, "titulo": f"row-{n}", "url": ""}
        for n, agent in [(3, "Cursor"), (1, "Cursor"), (2, "Cursor"), (5, "Codex"), (4, "Codex")]
    ])
    first = build_stratified_sample(frame.sample(frac=1, random_state=1), 7, "seed", 1)
    second = build_stratified_sample(frame.sample(frac=1, random_state=2), 7, "seed", 1)

    assert first == second
    assert len(first) == 2
    assert all(row["label"] is None and row["reviewer"] is None and row["reviewed_at"] is None for row in first)


def test_metrics_are_normalized_per_source_and_signal_without_weights():
    frame = pd.DataFrame([
        {"fuente": "github", "nombre_agente": "Cursor", "stars_github": 10},
        {"fuente": "github", "nombre_agente": "Codex", "stars_github": 20},
        {"fuente": "devto", "nombre_agente": "Cursor", "stars_github": 1000},
        {"fuente": "devto", "nombre_agente": "Codex", "stars_github": 2000},
    ])
    rows = build_source_metrics(frame, 7, metrics=["stars_github"])

    normalized = {(r["source"], r["agent"]): r["normalized_value"] for r in rows}
    assert normalized == {
        ("devto", "Codex"): 1.0,
        ("devto", "Cursor"): 0.0,
        ("github", "Codex"): 1.0,
        ("github", "Cursor"): 0.0,
    }
    assert all(row["normalization_method"] == "min_max_within_source_metric" for row in rows)


def test_quality_publication_marks_run_last_and_failed_never_updates_latest(tmp_path):
    legacy = tmp_path / "quality_summary.csv"
    legacy.write_text("old\n", encoding="utf-8")
    tables = {"quality_summary": pd.DataFrame([{"run_id": 7, "value": 1}])}

    publication = publish_quality_evidence(7, tables, "success", tmp_path / "runs", tmp_path)
    assert publication.marker_file.exists()
    assert legacy.read_text(encoding="utf-8").startswith("run_id,value")

    publish_quality_evidence(8, tables, "failed", tmp_path / "runs", tmp_path)
    assert legacy.read_text(encoding="utf-8").startswith("run_id,value")
    assert '"run_id": "7"' in (tmp_path / "quality_latest.json").read_text(encoding="utf-8")


def test_empty_extraction_run_does_not_replace_useful_legacy_evidence(tmp_path):
    legacy = tmp_path / "source_execution_evidence.csv"
    legacy.write_text("useful\n", encoding="utf-8")
    run = EvidenceRun("empty-run", tmp_path / "runs", legacy)
    run.record(ExtractionResult(source="google_trends", status="empty"))

    publication = run.publish("empty")

    assert publication.summary_file.exists()
    assert legacy.read_text(encoding="utf-8") == "useful\n"
