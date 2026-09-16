"""Offline contracts for independently scheduled GitHub/main ETLs."""
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from src.loaders import load_raw_to_db as raw
from src.scripts import run_pipeline as runner
from src.scripts import run_github_pipeline as github_runner
from src.staging import stg_build_unified as staging
from src.utils import pipeline_scope
from src.utils.extraction_evidence import EvidenceRun, log_source_execution


EXTRACTORS = [
    "extract_github_repos", "extract_hackernews", "extract_devto", "extract_reddit",
    "extract_trends", "extract_aidedev_catalog",
    "extract_stackoverflow", "extract_arxiv", "extract_gnews",
]


@pytest.mark.parametrize("profile", ["main", "github", "all"])
def test_extraction_calls_only_owned_sources(monkeypatch, profile):
    extractors = {}
    for name in EXTRACTORS:
        extractors[name] = MagicMock(return_value=None)
        monkeypatch.setattr(runner, name, extractors[name])
    fallback = MagicMock()
    monkeypatch.setattr(runner, "extract_and_validate_catalog", fallback)
    runner.run_extraction_phase(42, "2026-09-01", "2026-09-16", pipeline=profile)
    for name, extractor in extractors.items():
        expected = profile == "all" or (name == "extract_github_repos") == (profile == "github")
        assert extractor.call_count == int(expected)
    fallback.assert_not_called()
    if profile != "main":
        assert extractors["extract_github_repos"].call_args.kwargs == {
            "pages": 10, "per_page": 100, "run_id": 42,
            "start_date": "2026-09-01", "end_date": "2026-09-16",
        }


def test_main_default_never_extracts_github(monkeypatch):
    for name in EXTRACTORS:
        monkeypatch.setattr(runner, name, MagicMock(return_value=None))
    runner.run_extraction_phase(42)
    runner.extract_github_repos.assert_not_called()
    runner.extract_hackernews.assert_called_once_with(run_id=42)


@pytest.mark.parametrize("profile", ["main", "github", "all"])
def test_retired_survey_is_never_extracted(monkeypatch, profile):
    for name in EXTRACTORS:
        monkeypatch.setattr(runner, name, MagicMock(return_value=None))
    survey = MagicMock(side_effect=AssertionError("Survey extraction is retired"))
    # Also catch a future reintroduction through a directly imported alias.
    monkeypatch.setattr(runner, "extract_google_forms_survey", survey, raising=False)
    runner.run_extraction_phase(42, pipeline=profile)
    survey.assert_not_called()


def test_loader_scopes_history_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(raw, "RAW_DIR", tmp_path)
    files = {}
    for source in ("github", "devto", "catalogo"):
        directory = tmp_path / source
        directory.mkdir()
        files[source] = directory / "snapshot.json"
        files[source].write_text('[{"id": 1}]')
    assert raw.select_raw_files("github") == [files["github"]]
    assert set(raw.select_raw_files("main")) == {files["devto"], files["catalogo"]}
    assert raw.select_raw_files("github", []) == []
    assert raw.select_raw_files("main", [files["devto"], files["devto"]]) == [files["devto"]]
    with pytest.raises(ValueError, match="does not belong"):
        raw.select_raw_files("main", [files["github"]])
    with pytest.raises(ValueError, match="outside"):
        raw.select_raw_files("github", [tmp_path.parent / "outside.json"])
    with pytest.raises(ValueError, match="Missing"):
        raw.select_raw_files("github", [tmp_path / "github" / "missing.json"])


@pytest.fixture
def orchestrator(monkeypatch, tmp_path):
    events = []
    publications = []
    monkeypatch.setattr(runner, "start_pipeline_audit", lambda: 42)
    end = MagicMock()
    monkeypatch.setattr(runner, "end_pipeline_audit", end)

    def evidence(run_id, **kwargs):
        run = EvidenceRun(run_id, tmp_path / "runs", tmp_path / "latest.csv", **kwargs)
        publications.append(run)
        return run
    monkeypatch.setattr(runner, "EvidenceRun", evidence)

    @contextmanager
    def lock(run_id):
        events.append("lock")
        try:
            yield
        finally:
            events.append("unlock")
    monkeypatch.setattr(runner, "processing_lock", lock)
    mocks = {}
    for name in ("run_loader", "run_staging_pipeline", "run_quality_framework", "run_gold_phase", "run_gold_quality"):
        def phase(*args, _name=name, **kwargs):
            events.append(_name)
            if _name == "run_quality_framework":
                return {"quality_summary": [{"total_raw_records": 1, "load_error_records": 0}]}
        mocks[name] = MagicMock(side_effect=phase)
        monkeypatch.setattr(runner, name, mocks[name])
    return events, publications, mocks, end


@pytest.mark.parametrize("profile", ["main", "github"])
def test_full_etl_passes_scope_and_only_current_raw_manifest(monkeypatch, orchestrator, profile):
    events, publications, mocks, end = orchestrator
    source = "github" if profile == "github" else "devto"

    def extract(run_id, **kwargs):
        assert kwargs["pipeline"] == profile
        events.append("extract")
        log_source_execution(source, "success", 1, raw_path=f"/raw/{source}/current.json", run_id=run_id)
    monkeypatch.setattr(runner, "run_extraction_phase", extract)
    (github_runner.main if profile == "github" else runner.main)([])
    assert events == ["extract", "lock", "run_loader", "run_staging_pipeline",
                      "run_quality_framework", "run_gold_phase", "run_gold_quality", "unlock"]
    mocks["run_loader"].assert_called_once_with(run_id=42, pipeline=profile,
                                               file_paths=[f"/raw/{source}/current.json"])
    mocks["run_staging_pipeline"].assert_called_once_with(run_id=42, rebuild=False, pipeline=profile)
    mocks["run_gold_phase"].assert_called_once_with(42, rebuild=False, pipeline=profile)
    assert end.call_args.kwargs["status"] == "success"
    summary = json.loads((publications[0].run_directory / "summary.json").read_text())
    assert summary["pipeline"] == profile


def test_github_failure_is_nonzero_and_never_loads_other_sources(monkeypatch, orchestrator):
    events, publications, mocks, end = orchestrator
    def extract(run_id, **kwargs):
        log_source_execution("github", "failed", run_id=run_id)
    monkeypatch.setattr(runner, "run_extraction_phase", extract)
    with pytest.raises(RuntimeError, match="Extraction failed"):
        github_runner.main([])
    assert events == []
    mocks["run_loader"].assert_not_called()
    assert end.call_args.kwargs["status"] == "failed"


def test_partial_github_data_remains_partial(monkeypatch, orchestrator):
    _, _, _, end = orchestrator
    def extract(run_id, **kwargs):
        log_source_execution("github", "partial_success", 1, run_id=run_id)
    monkeypatch.setattr(runner, "run_extraction_phase", extract)
    github_runner.main([])
    assert end.call_args.kwargs["status"] == "partial_success"


def test_extract_only_never_takes_processing_lock(monkeypatch, orchestrator):
    events, _, mocks, _ = orchestrator
    monkeypatch.setattr(runner, "run_extraction_phase", lambda *a, **k: None)
    github_runner.main(["--phase", "extract"])
    assert events == []
    mocks["run_loader"].assert_not_called()


def test_process_resolves_owned_run_without_extracting(monkeypatch, orchestrator):
    _, _, mocks, _ = orchestrator
    resolver = MagicMock(return_value=7)
    extract = MagicMock()
    monkeypatch.setattr(runner, "resolve_data_run_id", resolver)
    monkeypatch.setattr(runner, "run_extraction_phase", extract)
    github_runner.main(["--phase", "process", "--data-run-id", "7"])
    resolver.assert_called_once_with(7, pipeline="github")
    extract.assert_not_called()
    mocks["run_loader"].assert_not_called()
    assert mocks["run_quality_framework"].call_args.kwargs["data_run_id"] == 7


@pytest.mark.parametrize("arguments", [
    ["--pipeline", "main"], ["--pipeline", "all"],
    ["--staging-mode", "rebuild"], ["--gold-mode", "rebuild"],
    ["--github-since", "2026-09-17", "--date", "2026-09-16"],
])
def test_micro_cli_rejects_cross_scope_and_destructive_options(arguments, monkeypatch):
    audit = MagicMock()
    monkeypatch.setattr(runner, "start_pipeline_audit", audit)
    with pytest.raises(SystemExit) as error:
        github_runner.main(arguments)
    assert error.value.code == 2
    audit.assert_not_called()


@pytest.mark.parametrize("profile", ["main", "github"])
def test_scoped_rebuild_also_rejected_by_functions(profile):
    with pytest.raises(ValueError, match="rebuild"):
        staging.run_staging_pipeline(rebuild=True, pipeline=profile)
    with pytest.raises(ValueError, match="rebuild"):
        runner.run_gold_phase(42, rebuild=True, pipeline=profile)


@pytest.mark.parametrize("fail", [False, True])
def test_processing_lock_released_on_success_and_failure(monkeypatch, fail):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    monkeypatch.setattr(pipeline_scope.db_connector, "engine", engine)
    try:
        with pipeline_scope.processing_lock(42):
            if fail:
                raise RuntimeError("phase failed")
    except RuntimeError:
        assert fail
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements == ["SELECT pg_advisory_lock(:key)", "SELECT pg_advisory_unlock(:key)"]
    assert connection.commit.call_count == 2


def test_failed_unlock_discards_session(monkeypatch):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect = [None, RuntimeError("lost connection")]
    monkeypatch.setattr(pipeline_scope.db_connector, "engine", engine)
    with pytest.raises(RuntimeError, match="lost connection"):
        with pipeline_scope.processing_lock(42):
            pass
    connection.invalidate.assert_called_once()


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.prod.yml"])
def test_compose_has_independent_github_worker(filename):
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root / filename).read_text(encoding="utf-8"))["services"]
    main, github = services["etl"], services["etl-github"]
    assert main["build"] == github["build"]
    assert "github" in github["container_name"]
    assert github["entrypoint"][-1] == "src.scripts.run_github_pipeline"
    assert "GITHUB_TOKEN" not in main["environment"]
    assert "GITHUB_TOKEN" in github["environment"]
    assert "./etl/logs/github:/app/logs" in github["volumes"]
    assert "./etl/docs/github:/app/docs" in github["volumes"]
    assert github["profiles"] == ["etl-github"]


def test_gold_loaders_use_transaction_local_source_scope():
    root = Path(__file__).resolve().parents[1]
    for name, count in [("02_load_gold_dimensions.sql", 6), ("03_load_gold_fact.sql", 1)]:
        sql = (root / "sql" / name).read_text(encoding="utf-8")
        assert sql.count("current_setting('etl.pipeline', true)") == count
        assert sql.count("WHEN 'github' THEN fuente = 'github'") == count
        assert sql.count("WHEN 'main' THEN COALESCE(fuente, '') <> 'github'") == count


@pytest.mark.parametrize("profile", ["main", "github"])
def test_staging_filters_pending_files_and_versions_by_source(monkeypatch, profile):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.scalars.return_value.all.return_value = []
    connection.execute.return_value.fetchall.return_value = []
    monkeypatch.setattr(staging.db_connector, "engine", engine)
    monkeypatch.setattr(staging, "_ensure_staging_schema", lambda conn: None)
    assert staging.run_staging_pipeline(42, pipeline=profile)["processed_files"] == 0
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert len(statements) == 2
    assert all(f"WHERE {pipeline_scope.source_predicate(profile)}" in sql for sql in statements)


def test_gold_sets_scope_before_running_shared_sql(monkeypatch):
    engine = MagicMock()
    cursor = engine.begin.return_value.__enter__.return_value.connection.cursor.return_value
    cursor.fetchone.return_value = (0,)
    monkeypatch.setattr(runner.db_connector, "engine", engine)
    runner.run_gold_phase(42, pipeline="github")
    assert cursor.execute.call_args_list[0].args == (
        "SELECT set_config('etl.pipeline', %s, true)", ("github",),
    )
    assert any("WHERE (fuente = 'github')" in str(call.args[0]) for call in cursor.execute.call_args_list)
