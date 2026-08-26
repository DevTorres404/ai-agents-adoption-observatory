import argparse
import datetime
import os
from contextlib import nullcontext
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.error_log import log_error
from src.utils.extraction_evidence import (
    EvidenceRun,
    ExtractionStatus,
    aggregate_status,
    evidence_context,
    log_source_execution,
    new_local_run_id,
)

from src.extractors.github import extract_github_repos
from src.extractors.hackernews import extract_hackernews
from src.extractors.devto import extract_devto
from src.extractors.reddit import extract_reddit
from src.extractors.google_trends import extract_trends
from src.extractors.file_catalog import extract_and_validate_catalog
from src.extractors.aidedev import extract_aidedev_catalog
from src.extractors.fuente_propia import extract_google_forms_survey
from src.extractors.stackoverflow import extract_stackoverflow
from src.extractors.arxiv import extract_arxiv
from src.extractors.gnews import extract_gnews
from src.loaders.load_raw_to_db import run_loader
from src.staging.stg_build_unified import run_staging_pipeline
from src.quality.quality_metrics import run_quality_framework

def start_pipeline_audit():
    """Inserta registro inicial en audit.pipeline_runs y devuelve el run_id"""
    if not db_connector.engine:
        return None
    try:
        with db_connector.engine.begin() as conn:
            query = text("""
                INSERT INTO audit.pipeline_runs (status) 
                VALUES ('running') 
                RETURNING run_id
            """)
            run_id = conn.execute(query).scalar()
            return run_id
    except Exception as e:
        global_logger.error(f"Fallo al registrar inicio de auditoría: {e}")
        return None

def end_pipeline_audit(run_id, status="completed", error_msg=None):
    """Cierra el run con conteos actuales, sin reutilizar resúmenes históricos."""
    if not db_connector.engine or not run_id:
        return
        
    try:
        with db_connector.engine.begin() as conn:
            # Cada run debe reflejar el estado materializado de la BD al cerrar.
            # quality_summary puede pertenecer a otra ejecución y no es una
            # fuente válida para auditar el run actual.
            counts = conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM raw.raw_records) AS raw_records,
                    (SELECT COUNT(*) FROM staging.stg_actividad_agente_ia) AS staging_records
            """)).one()

            raw_recs = int(counts.raw_records or 0)
            stg_recs = int(counts.staging_records or 0)
            dropped = max(raw_recs - stg_recs, 0)
            comp_rate = round((stg_recs / raw_recs) * 100, 2) if raw_recs else 0.0
            
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

def run_extraction_phase(run_id):
    global_logger.info("=== FASE 1: EXTRACCIÓN MÚLTIPLE ===")
    
    # 1. GitHub API
    try:
        extract_github_repos(pages=15, per_page=100, run_id=run_id)
    except Exception as e:
        _record_extractor_exception("github", e, run_id)

    # 2. HackerNews (BS4)
    try:
        extract_hackernews()
    except Exception as e:
        _record_extractor_exception("hackernews", e, run_id)

    # 3. DevTo (BS4)
    try:
        extract_devto(max_records=2000)
    except Exception as e:
        _record_extractor_exception("devto", e, run_id)
        
    # 4. Reddit (Playwright)
    try:
        extract_reddit(max_records=1000)
    except Exception as e:
        _record_extractor_exception("reddit", e, run_id)
        
    # 5. Google Trends (pytrends)
    try:
        extract_trends()
    except Exception as e:
        _record_extractor_exception("google_trends", e, run_id)

    # 6. Catálogo estructurado AIDev (con respaldo manual)
    try:
        extract_aidedev_catalog()
    except Exception as e:
        _record_extractor_exception("aidedev", e, run_id)
        try:
            extract_and_validate_catalog()
        except Exception as fallback_error:
            _record_extractor_exception("file_catalog", fallback_error, run_id)

    # 7. Fuente propia: encuesta Google Forms
    try:
        extract_google_forms_survey()
    except Exception as e:
        _record_extractor_exception("fuente_propia", e, run_id)

    # 8. StackOverflow
    try:
        extract_stackoverflow(max_per_agent=500)
    except Exception as e:
        _record_extractor_exception("stackoverflow", e, run_id)

    # 9. arXiv
    try:
        extract_arxiv(max_per_agent=1000)
    except Exception as e:
        _record_extractor_exception("arxiv", e, run_id)

    # 10. Google News
    try:
        extract_gnews(run_id=run_id)
    except Exception as e:
        _record_extractor_exception("gnews", e, run_id)

def run_gold_phase(run_id):
    global_logger.info("=== FASE 5: CARGA DATA WAREHOUSE GOLD ===")
    if not db_connector.engine:
        raise Exception("Sin conexión a BD para la fase Gold")
        
    etl_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    migration_path = os.path.join(etl_dir, "sql", "07_add_semantic_staging_columns.sql")
    scripts = [
        os.path.join(etl_dir, "sql", "02_load_gold_dimensions.sql"),
        os.path.join(etl_dir, "sql", "03_load_gold_fact.sql"),
        os.path.join(etl_dir, "sql", "04_create_kpi_views.sql")
    ]
    
    # Ejecutamos todo dentro de una transaccion
    with db_connector.engine.begin() as conn:
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        global_logger.info(f"Ejecutando {migration_path}...")
        with open(migration_path, 'r', encoding='utf-8') as migration_file:
            cursor.execute(migration_file.read())

        cursor.execute("""
            SELECT COUNT(*)
            FROM staging.stg_actividad_agente_ia
            WHERE dim_nombre_plataforma IS NULL
               OR dim_nombre_tecnologia IS NULL
               OR dim_nombre_comunidad IS NULL
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

def main():
    parser = argparse.ArgumentParser(description="Orquestador Maestro del Pipeline ETL Observatorio IA")
    parser.add_argument("--date", type=str, help="Fecha de ejecución (YYYY-MM-DD)", default=datetime.date.today().strftime("%Y-%m-%d"))
    parser.add_argument("--phase", type=str, choices=["all", "extract", "load", "staging", "quality", "gold"], default="all", help="Ejecutar solo una fase específica")
    args = parser.parse_args()
    
    global_logger.info(f">>> INICIANDO PIPELINE UNIFICADO (Fecha Objetivo: {args.date}) <<<")
    run_id = start_pipeline_audit()
    includes_extraction = args.phase in ["all", "extract"]
    evidence_run = EvidenceRun(run_id or new_local_run_id()) if includes_extraction else None
    evidence_scope = evidence_context(evidence_run) if evidence_run else nullcontext()

    with evidence_scope:
        try:
            if includes_extraction:
                run_extraction_phase(run_id)

            if args.phase in ["all", "load"]:
                global_logger.info("=== FASE 2: CARGA RAW A BD ===")
                run_loader()

            if args.phase in ["all", "staging"]:
                global_logger.info("=== FASE 3: STAGING ===")
                run_staging_pipeline()

            if args.phase in ["all", "quality"]:
                global_logger.info("=== FASE 4: CALIDAD DE DATOS ===")
                run_quality_framework()

            if args.phase in ["all", "gold"]:
                run_gold_phase(run_id)
                run_gold_quality(run_id)

            status = (
                derive_pipeline_status(evidence_run.results)
                if evidence_run
                else ExtractionStatus.SUCCESS.value
            )
            error_msg = "Una o más fuentes tuvieron incidentes" if status == "partial_success" else None
            end_pipeline_audit(run_id, status=status, error_msg=error_msg)
            if evidence_run:
                evidence_run.publish(status)
            global_logger.info(
                f">>> PIPELINE UNIFICADO FINALIZADO status={status} (Run ID: {run_id}) <<<"
            )

        except Exception as e:
            error_str = f"Fallo Crítico: {str(e)}"
            global_logger.error(error_str)
            end_pipeline_audit(run_id, status="failed", error_msg=error_str)
            if evidence_run:
                evidence_run.publish(ExtractionStatus.FAILED)
            raise

if __name__ == "__main__":
    main()
