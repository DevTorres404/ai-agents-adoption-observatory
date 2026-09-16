"""Destructive fixture data: opt in ONLY with a disposable PostgreSQL database."""
import json
import os
import uuid
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    os.getenv("ETL_ISOLATED_RECOVERY") != "1",
    reason="Requires ETL_ISOLATED_RECOVERY=1 and a disposable DATABASE_URL",
)


def test_raw_process_and_reaudit_on_real_postgres(tmp_path, monkeypatch):
    from src.loaders import load_raw_to_db as raw
    from src.quality import quality_metrics as quality
    from src.scripts import run_pipeline as pipeline
    from src.staging import stg_build_unified as staging
    from src.staging import stg_llm_enrichment as llm
    from src.utils.db import db_connector

    engine = create_engine(os.environ["DATABASE_URL"])
    monkeypatch.setattr(db_connector, "engine", engine)
    monkeypatch.setattr(raw, "RAW_DIR", tmp_path / "raw")
    for module in (raw, quality, staging):
        monkeypatch.setattr(module, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(llm, "CACHE_FILE", tmp_path / "llm_cache.json")
    def offline_llm(*args, **kwargs):
        raise requests.ConnectionError("Ollama intentionally disabled in isolated integration")
    monkeypatch.setattr(llm.requests, "get", offline_llm)
    root = Path(__file__).resolve().parents[1]
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for name in ("08_incremental_staging.sql", "09_incremental_gold.sql", "10_quality_governance.sql"):
                script = (root / "sql" / name).read_text(encoding="utf-8")
                conn.exec_driver_sql(script)
                conn.exec_driver_sql(script)

        directory = tmp_path / "raw" / "github"
        directory.mkdir(parents=True)
        (directory / "fixture.json").write_text(json.dumps({"fixture": str(uuid.uuid4()), "items": [
            {"id": 900001, "name": "Codex", "description": "Codex Python agent",
             "created_at": "2026-09-01T00:00:00Z", "html_url": "https://example.test/codex",
             "stargazers_count": 10, "forks_count": 2},
            {"id": 900002, "name": "Cursor", "description": "Cursor AI editor",
             "created_at": "2026-09-02T00:00:00Z", "html_url": "https://example.test/cursor",
             "stargazers_count": 20, "forks_count": 1},
        ]}), encoding="utf-8")
        other_directory = tmp_path / "raw" / "devto"
        other_directory.mkdir()
        (other_directory / "fixture.json").write_text(json.dumps([{
            "id": 900003, "title": "Codex Python tutorial", "description": "Codex agent",
            "created_at": "2026-09-03T00:00:00Z", "url": "https://example.test/devto",
            "reactions_count": 3, "comments_count": 1,
        }]), encoding="utf-8")
        pipeline.main(["--pipeline", "github", "--phase", "load"])
        data_run_id = quality.resolve_data_run_id(pipeline="github")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM raw.raw_files WHERE fuente = 'devto'")).scalar() == 0
        pipeline.main(["--phase", "load"])
        main_data_run_id = quality.resolve_data_run_id(pipeline="main")
        assert main_data_run_id != data_run_id
        pipeline.main(["--pipeline", "github", "--phase", "process", "--data-run-id", str(data_run_id)])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia WHERE transformation_version IS NULL")).scalar() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia")).scalar() == 2
            assert conn.execute(text("SELECT COUNT(*) FROM gold.fact_actividad_agente_ia")).scalar() == 2
            first_keys = conn.execute(text("SELECT id_fact_actividad, fact_lineage_key FROM gold.fact_actividad_agente_ia ORDER BY 1")).all()
        pipeline.main(["--pipeline", "github", "--phase", "process", "--data-run-id", str(data_run_id)])
        pipeline.main(["--pipeline", "github", "--phase", "quality", "--data-run-id", str(data_run_id)])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT id_fact_actividad, fact_lineage_key FROM gold.fact_actividad_agente_ia ORDER BY 1")).all() == first_keys
            summaries = conn.execute(text("SELECT run_id, data_run_id, total_raw_records, total_staging_records, completion_rate FROM audit.quality_summary WHERE data_run_id = :data_run_id ORDER BY run_id"), {"data_run_id": data_run_id}).all()
            assert len(summaries) == 3
            assert all(row.data_run_id == data_run_id and row.run_id != data_run_id for row in summaries)
            assert all(row.total_raw_records == 2 and row.total_staging_records == 2 and row.completion_rate == 100 for row in summaries)
            assert conn.execute(text("SELECT COUNT(*) FROM audit.pipeline_runs WHERE run_id >= :run_id AND status != 'success'"), {"run_id": data_run_id}).scalar() == 0
        # Main's pending Raw must not have been transformed by the GitHub job.
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia WHERE fuente = 'devto'")).scalar() == 0
        pipeline.main(["--phase", "staging"])
        # Even when foreign Staging exists, GitHub must not publish it in Gold.
        pipeline.main(["--pipeline", "github", "--phase", "gold"])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM gold.fact_actividad_agente_ia")).scalar() == 2
        pipeline.main(["--phase", "process"])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM gold.fact_actividad_agente_ia")).scalar() == 3
            retained = conn.execute(text("""
                SELECT f.id_fact_actividad, f.fact_lineage_key FROM gold.fact_actividad_agente_ia f
                JOIN gold.dim_fuente d ON d.id_fuente = f.id_fuente
                WHERE d.nombre_fuente = 'github' ORDER BY 1
            """)).all()
            assert retained == first_keys
            assert conn.execute(text("SELECT data_run_id FROM audit.quality_summary ORDER BY run_id DESC LIMIT 1")).scalar() == main_data_run_id
    finally:
        quality.build_candidate_staging_frame.cache_clear()
        engine.dispose()
