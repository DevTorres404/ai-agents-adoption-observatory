import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, text

from src.loaders import load_raw_to_db as raw
from src.quality import quality_metrics as quality
from src.scripts import run_pipeline as pipeline
from src.extractors import github
from src.quality.governance import reconcile_quality_counts
from src.utils.extraction_evidence import EvidenceRun, evidence_context


@pytest.fixture
def raw_database(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS raw")
        conn.exec_driver_sql("""CREATE TABLE raw.raw_files (
            id INTEGER PRIMARY KEY, fuente TEXT, tipo_fuente TEXT,
            ruta_relativa TEXT, nombre_archivo TEXT, cantidad_registros INTEGER,
            cantidad_columnas INTEGER, tamano_bytes INTEGER,
            hash_sha256 TEXT UNIQUE, run_id INTEGER)""")
        conn.exec_driver_sql("""CREATE TABLE raw.raw_records (
            id INTEGER PRIMARY KEY, file_id INTEGER, raw_data TEXT, run_id INTEGER)""")
    monkeypatch.setattr(raw.db_connector, "engine", engine)
    monkeypatch.setattr(raw, "RAW_DIR", tmp_path)
    monkeypatch.setattr(raw, "export_full_raw_inventory", lambda **kwargs: None)
    yield engine, tmp_path
    engine.dispose()


def test_raw_real_sqlalchemy_transaction_and_batched_inserts(raw_database):
    engine, directory = raw_database
    (directory / "sample.json").write_text(json.dumps([{"id": n} for n in range(2501)]))
    record_calls = []
    @event.listens_for(engine, "before_cursor_execute")
    def record(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO raw.raw_records" in statement:
            record_calls.append(statement)
    result = raw.run_loader(run_id=42)
    assert result["loaded_files"] == 1
    assert len(record_calls) == 3
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM raw.raw_records")).scalar() == 2501
    assert raw.run_loader(run_id=43)["skipped_files"] == 1


def test_raw_rolls_back_and_propagates_failure_with_run_id(raw_database):
    engine, directory = raw_database
    (directory / "sample.json").write_text('[{"id": 1}]')
    def fail(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO raw.raw_records" in statement:
            raise RuntimeError("simulated record failure")
    event.listen(engine, "before_cursor_execute", fail)
    with patch.object(raw, "log_error") as log, pytest.raises(RuntimeError, match="Raw"):
        raw.run_loader(run_id=42)
    assert log.call_args.kwargs["run_id"] == 42
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM raw.raw_files")).scalar() == 0
    event.remove(engine, "before_cursor_execute", fail)
    assert raw.run_loader(run_id=42)["loaded_files"] == 1


def test_invalid_json_is_not_committed_as_empty(raw_database):
    engine, directory = raw_database
    (directory / "broken.json").write_text('{broken')
    with pytest.raises(RuntimeError, match="Raw"):
        raw.run_loader(run_id=42)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM raw.raw_files")).scalar() == 0


def test_raw_missing_engine_fails():
    with pytest.raises(RuntimeError):
        raw.run_loader(run_id=42)


def test_quality_cli_targets_existing_data_without_rewriting_original_run(monkeypatch):
    monkeypatch.setattr("sys.argv", ["etl", "--phase", "quality", "--data-run-id", "7"])
    datasets = {"quality_summary": [{"total_raw_records": 10, "load_error_records": 0}]}
    with (
        patch.object(pipeline, "start_pipeline_audit", return_value=99),
        patch.object(pipeline, "end_pipeline_audit") as end,
        patch.object(pipeline, "resolve_data_run_id", return_value=7) as resolve,
        patch.object(pipeline, "run_quality_framework", return_value=datasets) as run,
    ):
        pipeline.main()
    resolve.assert_called_once_with(7)
    assert run.call_args.kwargs["run_id"] == 99
    assert run.call_args.kwargs["data_run_id"] == 7
    assert end.call_args.args[0] == 99


def test_process_skips_extraction_and_raw_loading(monkeypatch):
    monkeypatch.setattr("sys.argv", ["etl", "--phase", "process", "--data-run-id", "7"])
    datasets = {"quality_summary": [{"total_raw_records": 10, "load_error_records": 0}]}
    with (
        patch.object(pipeline, "start_pipeline_audit", return_value=99),
        patch.object(pipeline, "end_pipeline_audit"),
        patch.object(pipeline, "resolve_data_run_id", return_value=7),
        patch.object(pipeline, "run_quality_framework", return_value=datasets),
        patch.object(pipeline, "run_extraction_phase") as extract,
        patch.object(pipeline, "run_loader") as load,
        patch.object(pipeline, "run_staging_pipeline") as staging,
        patch.object(pipeline, "run_gold_phase") as gold,
        patch.object(pipeline, "run_gold_quality"),
    ):
        pipeline.main()
    extract.assert_not_called()
    load.assert_not_called()
    staging.assert_called_once()
    gold.assert_called_once()


def test_raw_failure_marks_pipeline_failed(monkeypatch):
    monkeypatch.setattr("sys.argv", ["etl", "--phase", "load"])
    with (
        patch.object(pipeline, "start_pipeline_audit", return_value=99),
        patch.object(pipeline, "end_pipeline_audit") as end,
        patch.object(pipeline, "run_loader", side_effect=RuntimeError("Raw failed")),
        pytest.raises(RuntimeError),
    ):
        pipeline.main()
    assert end.call_args.kwargs["status"] == "failed"


def test_empty_quality_is_not_success():
    assert quality.quality_publication_status({"total_raw_records": 0}, "success") == "empty"
    assert quality.quality_publication_status({"total_raw_records": 0}, "failed") == "failed"
    assert quality.quality_publication_status({"total_raw_records": 3, "load_error_records": 1}, "success") == "failed"
    assert reconcile_quality_counts(0, 0, 0, 0)["completion_rate"] == 0


def test_resolve_latest_loaded_run_and_reject_empty_run(raw_database):
    engine, directory = raw_database
    (directory / "sample.json").write_text('[{"id": 1}]')
    raw.run_loader(run_id=7)
    assert quality.resolve_data_run_id() == 7
    assert quality.resolve_data_run_id(7) == 7
    with pytest.raises(ValueError, match="No loaded Raw data"):
        quality.resolve_data_run_id(99)


def test_quality_reads_data_run_but_persists_new_audit_run(monkeypatch, tmp_path):
    import pandas as pd
    engine = MagicMock()
    monkeypatch.setattr(quality.db_connector, "engine", engine)
    monkeypatch.setattr(quality, "ROOT_DIR", tmp_path)
    candidate = pd.DataFrame()
    summary = {"total_raw_records": 4, "load_error_records": 0}
    with (
        patch.object(quality, "build_candidate_staging_frame", return_value=candidate) as build,
        patch.object(quality, "get_overall_metrics", return_value=summary) as metrics,
        patch.object(quality, "get_nulls_matrix", return_value=[]) as nulls,
        patch.object(quality, "get_dedup_report", return_value=[]) as dedup,
        patch.object(quality, "get_casting_report", return_value=[]) as casting,
        patch.object(quality, "_staging_snapshot", return_value=candidate) as snapshot,
        patch.object(quality, "_previous_success", return_value={}),
        patch.object(quality, "_latest_freshness", return_value={}),
        patch.object(quality, "_issue_breakdown", return_value=[]),
        patch.object(quality, "get_homologation_map", return_value=[]),
        patch.object(quality, "get_staging_contract_report", return_value=[]),
        patch.object(quality, "_persist") as persist,
        patch.object(quality, "publish_quality_evidence") as publish,
    ):
        datasets = quality.run_quality_framework(run_id=99, data_run_id=7)
    for function in (build, metrics, nulls, dedup, casting):
        function.assert_called_once_with(7)
    assert snapshot.call_args.args[1] == 7
    assert persist.call_args.args[1] == 99
    assert publish.call_args.args[0] == 99
    assert datasets["quality_summary"][0]["data_run_id"] == 7


def test_quality_loss_stops_gold(monkeypatch):
    monkeypatch.setattr("sys.argv", ["etl", "--phase", "process"])
    with (
        patch.object(pipeline, "resolve_data_run_id", return_value=7),
        patch.object(pipeline, "start_pipeline_audit", return_value=99),
        patch.object(pipeline, "end_pipeline_audit") as end,
        patch.object(pipeline, "run_staging_pipeline"),
        patch.object(pipeline, "run_quality_framework", return_value={"quality_summary": [{"load_error_records": 2}]}),
        patch.object(pipeline, "run_gold_phase") as gold,
        pytest.raises(RuntimeError, match="missing Staging"),
    ):
        pipeline.main()
    gold.assert_not_called()
    assert end.call_args.kwargs["status"] == "failed"


def test_governance_migration_copies_cannot_drift():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "sql/10_quality_governance.sql").read_text(encoding="utf-8")
    assert migration == (root / "initdb/10_quality_governance.sql").read_text(encoding="utf-8")
    assert "data_run_id INTEGER REFERENCES audit.pipeline_runs(run_id)" in migration


def test_github_explicit_window_reaches_request_and_metadata(tmp_path):
    response = MagicMock()
    response.json.return_value = {"total_count": 1, "items": [{"id": 1}]}
    client = MagicMock()
    client.get.return_value = response
    client.last_status_code = 200
    run = EvidenceRun(7, tmp_path / "evidence", tmp_path / "legacy.csv")
    with (
        patch.object(github, "HttpClient", return_value=client),
        patch.object(github, "RAW_DIR", tmp_path / "raw"),
        evidence_context(run),
    ):
        result = github.extract_github_repos(queries=["Codex"], run_id=7,
            start_date="2026-09-01", end_date="2026-09-13")
    assert "created:2026-09-01..2026-09-13" in client.get.call_args.kwargs["params"]["q"]
    metadata = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))["metadata"]
    assert metadata["date_range_start"] == "2026-09-01"
    assert metadata["date_range_end"] == "2026-09-13"


def test_github_invalid_window_fails_before_http():
    with patch.object(github, "HttpClient") as http, pytest.raises(ValueError):
        github.extract_github_repos(start_date="2026-09-13", end_date="2026-09-01")
    http.assert_not_called()
