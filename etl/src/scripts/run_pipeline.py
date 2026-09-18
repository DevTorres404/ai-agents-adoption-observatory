import argparse
import json
import sys
import datetime
import os
import time
from contextlib import nullcontext
from contextlib import contextmanager
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.error_log import log_error
from src.utils.pipeline_scope import PIPELINES, includes_source, processing_lock, source_predicate, validate_pipeline
from src.utils.observatory_scope import ACTIVE_SOURCES, SUPPORTED_AGENTS, SCOPE
from src.utils.extraction_window import resolve_window, require_annual_window
from src.utils.time_utils import today_local
from src.utils.extraction_evidence import (
    EvidenceRun,
    ExtractionStatus,
    aggregate_status,
    evidence_context,
    log_source_execution,
    new_local_run_id,
)

from src.extractors.github import extract_github_repos
from src.extractors.google_trends import extract_trends
from src.extractors.aidedev import extract_aidedev_catalog
from src.extractors.hackernews import extract_hackernews
from src.loaders.load_raw_to_db import run_loader
from src.staging.stg_build_unified import run_staging_pipeline
from src.quality.quality_metrics import run_quality_framework, resolve_data_run_id, quality_publication_status


@contextmanager
def timed_phase(name, run_id):
    started = time.perf_counter()
    try:
        yield
    finally:
        global_logger.info(f"ETL timing run_id={run_id} phase={name} duration_seconds={time.perf_counter() - started:.3f}")

def start_pipeline_audit(run_config=None):
    """Inserta registro inicial en audit.pipeline_runs y devuelve el run_id"""
    if not db_connector.engine:
        raise RuntimeError("Pipeline audit requires a database connection")
    try:
        with db_connector.engine.begin() as conn:
            # Fail before expensive extraction if an existing volume was not migrated.
            conn.execute(text("SELECT data_run_id FROM audit.quality_summary LIMIT 0"))
            query = text("""
                INSERT INTO audit.pipeline_runs (status, run_config)
                VALUES ('running', CAST(:config AS JSONB))
                RETURNING run_id
            """)
            run_id = conn.execute(query, {"config": json.dumps(run_config or {})}).scalar()
            return run_id
    except Exception as e:
        global_logger.error(f"Fallo al registrar inicio de auditoría: {e}")
        raise RuntimeError("Audit preflight failed; verify DB connectivity and apply sql/10_quality_governance.sql and sql/13_source_run_config.sql") from e

def end_pipeline_audit(run_id, status="completed", error_msg=None):
    """Cierra el run con conteos actuales, sin reutilizar resúmenes históricos."""
    if not db_connector.engine or not run_id:
        return
        
    try:
        with db_connector.engine.begin() as conn:
            counts = conn.execute(text("""
                SELECT
                    COALESCE((SELECT total_raw_records FROM audit.quality_summary
                              WHERE run_id = :run_id ORDER BY id DESC LIMIT 1),
                             (SELECT COUNT(*) FROM raw.raw_records r JOIN raw.raw_files f ON f.id=r.file_id
                              WHERE COALESCE(r.run_id, f.run_id)=:run_id)) AS raw_records,
                    COALESCE((SELECT total_staging_records FROM audit.quality_summary
                              WHERE run_id = :run_id ORDER BY id DESC LIMIT 1),
                             (SELECT COUNT(*) FROM staging.stg_actividad_agente_ia s JOIN raw.raw_files f ON f.id=s.raw_file_id
                              WHERE f.run_id=:run_id)) AS staging_records,
                    (SELECT load_error_records FROM audit.quality_summary
                     WHERE run_id = :run_id ORDER BY id DESC LIMIT 1) AS load_errors,
                    (SELECT completion_rate FROM audit.quality_summary
                     WHERE run_id = :run_id ORDER BY id DESC LIMIT 1) AS quality_completion
            """), {"run_id": run_id}).one()

            raw_recs = int(counts.raw_records or 0)
            stg_recs = int(counts.staging_records or 0)
            dropped = int(counts.load_errors or 0)
            comp_rate = float(counts.quality_completion) if counts.quality_completion is not None else (round((stg_recs / raw_recs) * 100, 2) if raw_recs else 0.0)
            
            query = text("""
                UPDATE audit.pipeline_runs
                SET execution_end = CURRENT_TIMESTAMP,
                    status = :status,
                    error_message = :error_msg,
                    total_raw_records = :raw,
                    total_staging_records = :stg,
                    records_discarded = :dropped,
                    completion_rate = :rate
                WHERE run_id = :run_id
            """)
            conn.execute(query, {
                "status": status,
                "error_msg": error_msg,
                "raw": raw_recs,
                "stg": stg_recs,
                "dropped": dropped,
                "rate": comp_rate,
                "run_id": run_id
            })
    except Exception as e:
        global_logger.error(f"Fallo al registrar fin de auditoría: {e}")
        raise


def derive_pipeline_status(source_results, critical_failure=False):
    if critical_failure:
        return ExtractionStatus.FAILED.value
    return aggregate_status(source_results).value


def _record_extractor_exception(source, exc, run_id):
    log_error(
        source,
        type(exc).__name__,
        str(exc),
        "Continúa con siguiente extractor",
        run_id=run_id,
    )
    log_source_execution(
        source,
        ExtractionStatus.FAILED,
        notes=str(exc),
        run_id=run_id,
    )

def run_extraction_phase(run_id, github_start_date=None, github_end_date=None, pipeline="main",
                         start_date=None, end_date=None):
    """Dispatch only active, owned sources. No unbounded fallback datasets."""
    validate_pipeline(pipeline)
    extractors = {
        "github": (extract_github_repos, {"pages": 10, "per_page": 100,
                   "start_date": github_start_date or start_date,
                   "end_date": github_end_date or end_date}),
        "catalogo": (extract_aidedev_catalog, {"start_date": start_date, "end_date": end_date}),
        "google_trends": (extract_trends, {"start_date": start_date, "end_date": end_date}),
        "hackernews": (extract_hackernews, {
                          "start_date": start_date, "end_date": end_date}),
    }
    for source, (extractor, kwargs) in extractors.items():
        if includes_source(pipeline, source):
            try:
                extractor(run_id=run_id, **kwargs)
            except Exception as exc:
                _record_extractor_exception(source, exc, run_id)


def run_gold_phase(run_id, rebuild=False, pipeline="all"):
    predicate = source_predicate(pipeline, "fuente")
    if rebuild and pipeline != "all":
        raise ValueError("Gold rebuild requires --pipeline all (global maintenance)")
    global_logger.info("=== FASE 5: CARGA DATA WAREHOUSE GOLD ===")
    if not db_connector.engine:
        raise Exception("Sin conexión a BD para la fase Gold")
        
    etl_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    migration_paths = [
        os.path.join(etl_dir, "sql", "07_add_semantic_staging_columns.sql"),
        os.path.join(etl_dir, "sql", "09_incremental_gold.sql"),
    ]
    scripts = [
        os.path.join(etl_dir, "sql", "02_load_gold_dimensions.sql"),
        os.path.join(etl_dir, "sql", "03_load_gold_fact.sql")
    ]
    
    # Ejecutamos todo dentro de una transaccion
    with db_connector.engine.begin() as conn:
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        # Transaction-local scope read by the shared, directly executable SQL.
        cursor.execute("SELECT set_config('etl.pipeline', %s, true)", (pipeline,))
        cursor.execute("SELECT set_config('etl.active_sources', %s, true)", (','.join(sorted(source for source in ACTIVE_SOURCES if includes_source(pipeline, source))),))
        cursor.execute("SELECT set_config('etl.supported_agents', %s, true)", (','.join(SUPPORTED_AGENTS),))
        for migration_path in migration_paths:
            global_logger.info(f"Ejecutando {migration_path}...")
            with open(migration_path, 'r', encoding='utf-8') as migration_file:
                cursor.execute(migration_file.read())

        if rebuild:
            global_logger.info("Gold rebuild explícito: reiniciando hechos y dimensiones.")
            cursor.execute("""
                TRUNCATE TABLE
                    gold.fact_actividad_agente_ia,
                    gold.dim_tiempo,
                    gold.dim_agente,
                    gold.dim_fuente,
                    gold.dim_plataforma,
                    gold.dim_tecnologia,
                    gold.dim_comunidad
                RESTART IDENTITY CASCADE
            """)

        cursor.execute(f"""
            SELECT COUNT(*)
            FROM staging.stg_actividad_agente_ia
            WHERE ({predicate}) AND (dim_nombre_plataforma IS NULL
               OR dim_nombre_tecnologia IS NULL
               OR dim_nombre_comunidad IS NULL)
        """)
        pending_semantic_rows = cursor.fetchone()[0]
        if pending_semantic_rows > 0:
            raise Exception(
                f"Staging contiene {pending_semantic_rows} registros sin enriquecimiento semántico. "
                "Ejecute primero la fase staging antes de cargar Gold."
            )

        for script_path in scripts:
            global_logger.info(f"Ejecutando {script_path}...")
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                cursor.execute(sql_script)
            except Exception as e:
                log_error("gold_loader", script_path, str(e), "Error critico en carga Gold", run_id=run_id)
                raise
        cursor.close()

def run_gold_quality(run_id):
    global_logger.info("=== FASE 6: CALIDAD GOLD ===")
    if not db_connector.engine:
        raise Exception("Sin conexión a BD para calidad Gold")
        
    try:
        with db_connector.engine.connect() as conn:
            # 1. Filas Staging vs Gold
            staging_rows = conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia")).scalar()
            gold_rows = conn.execute(text("SELECT COUNT(*) FROM gold.fact_actividad_agente_ia")).scalar()
            global_logger.info(f"Calidad Gold - Filas Staging: {staging_rows}, Filas Gold: {gold_rows}")
            
            # 2. Claves foraneas invalidas
            fk_query = """
            SELECT
                SUM(CASE WHEN da.id_agente IS NULL THEN 1 ELSE 0 END) +
                SUM(CASE WHEN df.id_fuente IS NULL THEN 1 ELSE 0 END) +
                SUM(CASE WHEN dt.id_tiempo IS NULL THEN 1 ELSE 0 END) +
                SUM(CASE WHEN dp.id_plataforma IS NULL THEN 1 ELSE 0 END) +
                SUM(CASE WHEN dtec.id_tecnologia IS NULL THEN 1 ELSE 0 END) +
                SUM(CASE WHEN dc.id_comunidad IS NULL THEN 1 ELSE 0 END) AS invalid_fks
            FROM gold.fact_actividad_agente_ia f
            LEFT JOIN gold.dim_agente da ON da.id_agente = f.id_agente
            LEFT JOIN gold.dim_fuente df ON df.id_fuente = f.id_fuente
            LEFT JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
            LEFT JOIN gold.dim_plataforma dp ON dp.id_plataforma = f.id_plataforma
            LEFT JOIN gold.dim_tecnologia dtec ON dtec.id_tecnologia = f.id_tecnologia
            LEFT JOIN gold.dim_comunidad dc ON dc.id_comunidad = f.id_comunidad;
            """
            invalid_fks = conn.execute(text(fk_query)).scalar()
            if invalid_fks is not None and invalid_fks > 0:
                raise Exception(f"Se encontraron {invalid_fks} registros con FKs invalidas en la Fact.")
            
            # 3. Valores nulos
            null_dates = conn.execute(text("SELECT COUNT(*) FROM gold.dim_tiempo WHERE fecha IS NULL")).scalar()
            if null_dates is not None and null_dates > 0:
                raise Exception(f"Se encontraron {null_dates} fechas nulas.")
                
            # 4. Valores negativos
            neg_metrics = conn.execute(text("SELECT COUNT(*) FROM gold.fact_actividad_agente_ia WHERE cantidad_menciones < 0 OR score_actividad < 0")).scalar()
            if neg_metrics is not None and neg_metrics > 0:
                raise Exception(f"Se encontraron {neg_metrics} metricas negativas.")
                
            # 5. Fecha Maxima
            max_date = conn.execute(text("SELECT MAX(fecha) FROM gold.dim_tiempo")).scalar()
            global_logger.info(f"Calidad Gold - Fecha Maxima Disponible: {max_date}")
            
            # 6. Duplicados por grano
            dups = conn.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT id_agente, id_fuente, id_plataforma, id_origen_registro
                    FROM gold.fact_actividad_agente_ia
                    GROUP BY id_agente, id_fuente, id_plataforma, id_origen_registro
                    HAVING COUNT(*) > 1
                ) sub
            """)).scalar()
            if dups is not None and dups > 0:
                raise Exception(f"Se encontraron {dups} violaciones al grano de la tabla de hechos.")
            
            global_logger.info("Calidad Gold validada exitosamente. El Data Warehouse es consistente y apto para BI.")
    except Exception as e:
        log_error("gold_quality", "validaciones", str(e), "Error critico en calidad Gold", run_id=run_id)
        raise

def main(argv=None, fixed_pipeline=None):
    parser = argparse.ArgumentParser(description="Orquestador Maestro del Pipeline ETL Observatorio IA")
    parser.add_argument("--pipeline", choices=PIPELINES, default=fixed_pipeline or "main",
                        help="main excluye GitHub; github lo aísla; all es mantenimiento global explícito")
    parser.add_argument("--date", type=datetime.date.fromisoformat, help="Fecha objetivo y límite superior de GitHub (YYYY-MM-DD)", default=today_local())
    parser.add_argument("--github-since", type=datetime.date.fromisoformat, help="Inicio explícito de created: para GitHub; no recupera actualizaciones de repos antiguos")
    parser.add_argument("--data-run-id", type=int, help="Corrida Raw a auditar con quality/process; por defecto la última cargada")
    parser.add_argument("--phase", type=str, choices=["all", "extract", "load", "staging", "quality", "gold", "process"], default="all", help="process reutiliza Raw: Staging + Calidad + Gold, sin extraer ni cargar archivos")
    parser.add_argument(
        "--staging-mode",
        choices=["incremental", "rebuild"],
        default="incremental",
        help="Use rebuild explicitly to discard and reconstruct all Staging rows.",
    )
    parser.add_argument(
        "--gold-mode",
        choices=["incremental", "rebuild"],
        default="incremental",
        help="Use rebuild explicitly to discard and reconstruct all Gold rows.",
    )
    parser.add_argument("--start-date", type=datetime.date.fromisoformat)
    parser.add_argument("--end-date", type=datetime.date.fromisoformat)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    explicit_window = any(value is not None for value in
                          (args.start_date, args.end_date, args.from_year, args.to_year))
    if explicit_window and args.phase not in {"all", "extract"}:
        parser.error("Los rangos se aplican a all/extract; process reutiliza los datos Raw existentes")
    if explicit_window and args.github_since:
        parser.error("No combine --github-since con los nuevos argumentos de rango")
    if explicit_window and any(arg == "--date" or arg.startswith("--date=") for arg in argv):
        parser.error("No combine --date con los nuevos argumentos de rango")
    try:
        window = resolve_window(args.start_date, args.end_date, args.from_year, args.to_year,
                                default_start=args.github_since, default_end=args.date)
        if includes_source(args.pipeline, "catalogo") and args.phase in {"all", "extract"}:
            require_annual_window(window)
    except ValueError as exc:
        parser.error(str(exc))
    if fixed_pipeline and args.pipeline != fixed_pipeline:
        parser.error(f"Este ejecutable solo permite --pipeline {fixed_pipeline}")
    if args.pipeline != "all" and (args.staging_mode == "rebuild" or args.gold_mode == "rebuild"):
        parser.error("rebuild requiere --pipeline all para no borrar datos del otro ETL")
    if args.data_run_id is not None and (args.phase not in {"quality", "process"} or args.data_run_id <= 0):
        parser.error("--data-run-id debe ser positivo y usarse con quality/process")
    if args.github_since and (args.pipeline not in {"github", "all"} or args.phase not in {"all", "extract"} or args.github_since > args.date):
        parser.error("--github-since requiere pipeline github/all, fase all/extract y una fecha no posterior a --date")
    
    global_logger.info(f">>> INICIANDO PIPELINE {args.pipeline} (Fecha Objetivo: {args.date}) <<<")
    data_run_id = None
    run_config = {
        "pipeline": args.pipeline, "sources": sorted(s for s in ACTIVE_SOURCES if includes_source(args.pipeline, s)),
        "phase": args.phase, "scope_version": SCOPE["version"],
        "window": window.as_dict() if args.phase in {"all", "extract"} else None,
        "data_run_id": args.data_run_id,
    }
    run_id = start_pipeline_audit(run_config)
    datasets = None
    includes_extraction = args.phase in ["all", "extract"]
    evidence_run = EvidenceRun(run_id or new_local_run_id(), pipeline=args.pipeline, run_config=run_config) if includes_extraction else None
    evidence_scope = evidence_context(evidence_run) if evidence_run else nullcontext()

    with evidence_scope:
        try:
            if includes_extraction:
                with timed_phase("extract", run_id):
                    run_extraction_phase(run_id,
                        start_date=window.start.isoformat(), end_date=window.end.isoformat(), pipeline=args.pipeline)
                if derive_pipeline_status(evidence_run.results) == ExtractionStatus.FAILED.value:
                    raise RuntimeError("Extraction failed; no downstream phases were executed")

            # Slow extraction never owns the warehouse lock.
            scope = processing_lock(run_id) if args.phase != "extract" else nullcontext()
            with scope:
                if args.phase in {"quality", "process"}:
                    data_run_id = resolve_data_run_id(args.data_run_id, pipeline=args.pipeline)
                if args.phase in ["all", "load"]:
                    global_logger.info("=== FASE 2: CARGA RAW A BD ===")
                    with timed_phase("load", run_id):
                        run_loader(run_id=run_id, pipeline=args.pipeline,
                                   file_paths=[r.raw_path for r in evidence_run.results if r.raw_path]
                                   if evidence_run else None)

                if args.phase in ["all", "staging", "process"]:
                    global_logger.info("=== FASE 3: STAGING ===")
                    with timed_phase("staging", run_id):
                        run_staging_pipeline(
                            run_id=run_id,
                            rebuild=args.staging_mode == "rebuild",
                            pipeline=args.pipeline,
                        )

                if args.phase in ["all", "quality", "process"]:
                    global_logger.info("=== FASE 4: CALIDAD DE DATOS ===")
                    quality_status = (
                        derive_pipeline_status(evidence_run.results)
                        if evidence_run else ExtractionStatus.SUCCESS.value
                    )
                    with timed_phase("quality", run_id):
                        datasets = run_quality_framework(
                            run_id=run_id, data_run_id=data_run_id,
                            source_results=evidence_run.results if evidence_run else None,
                            publication_status=quality_status,
                        )
                    if datasets["quality_summary"][0].get("load_error_records", 0) > 0:
                        raise RuntimeError("Quality detected missing Staging records; Gold was not executed")

                if args.phase in ["all", "gold", "process"]:
                    with timed_phase("gold", run_id):
                        run_gold_phase(run_id, rebuild=args.gold_mode == "rebuild", pipeline=args.pipeline)
                        run_gold_quality(run_id)

                status = (
                    derive_pipeline_status(evidence_run.results)
                    if evidence_run
                    else ExtractionStatus.SUCCESS.value
                )
                if datasets:
                    status = quality_publication_status(datasets["quality_summary"][0], status)
                error_msg = "Una o más fuentes tuvieron incidentes" if status == "partial_success" else None
                end_pipeline_audit(run_id, status=status, error_msg=error_msg)
                if evidence_run:
                    evidence_run.publish(status)
                global_logger.info(
                    f">>> PIPELINE {args.pipeline} FINALIZADO status={status} (Run ID: {run_id}) <<<"
                )

        except Exception as e:
            error_str = f"Fallo Crítico: {str(e)}"
            global_logger.error(error_str)
            try:
                end_pipeline_audit(run_id, status="failed", error_msg=error_str)
            except Exception:
                global_logger.exception("No se pudo cerrar la auditoría fallida")
            if evidence_run:
                evidence_run.publish(ExtractionStatus.FAILED)
            raise

if __name__ == "__main__":
    main()
