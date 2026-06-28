import argparse
import datetime
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.error_log import log_error

from src.extractors.github_api import extract_github_repos
from src.extractors.hackernews_scraper import extract_hackernews
from src.extractors.devto_scraper import extract_devto
from src.extractors.reddit_scraper import extract_reddit
from src.extractors.trends_scraper import extract_trends
from src.extractors.file_catalog import extract_and_validate_catalog
from src.extractors.aidedev_catalog import extract_aidedev_catalog

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
    """Actualiza el registro final con las métricas extraídas desde quality_summary"""
    if not db_connector.engine or not run_id:
        return
        
    try:
        with db_connector.engine.begin() as conn:
            # Recuperar las últimas métricas calculadas por Quality Framework
            metrics = conn.execute(text("SELECT * FROM audit.quality_summary ORDER BY id DESC LIMIT 1")).fetchone()
            
            raw_recs = metrics.total_raw_records if metrics else 0
            stg_recs = metrics.total_staging_records if metrics else 0
            dropped = metrics.total_duplicates_removed if metrics else 0
            comp_rate = metrics.completion_rate if metrics else 0.0
            
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

def run_extraction_phase(run_id):
    global_logger.info("=== FASE 1: EXTRACCIÓN MÚLTIPLE ===")
    
    # 1. GitHub API
    try:
        extract_github_repos(pages=1, per_page=20)
    except Exception as e:
        log_error("github_extractor", type(e).__name__, str(e), "Continúa con siguiente extractor", run_id=run_id)

    # 2. HackerNews (BS4)
    try:
        extract_hackernews()
    except Exception as e:
        log_error("hackernews_scraper", type(e).__name__, str(e), "Continúa con siguiente extractor", run_id=run_id)

    # 3. DevTo (BS4)
    try:
        extract_devto()
    except Exception as e:
        log_error("devto_scraper", type(e).__name__, str(e), "Continúa con siguiente extractor", run_id=run_id)
        
    # 4. Reddit (Playwright)
    try:
        extract_reddit()
    except Exception as e:
        log_error("reddit_scraper", type(e).__name__, str(e), "Continúa con siguiente extractor", run_id=run_id)
        
    # 5. Google Trends (pytrends)
    try:
        extract_trends()
    except Exception as e:
        log_error("trends_scraper", type(e).__name__, str(e), "Continúa con siguiente extractor", run_id=run_id)

    # 6. Catálogo estructurado AIDev (con respaldo manual)
    try:
        extract_aidedev_catalog()
    except Exception as e:
        log_error("aidedev_catalog", type(e).__name__, str(e), "Se intenta catálogo manual como respaldo", run_id=run_id)
        try:
            extract_and_validate_catalog()
        except Exception as fallback_error:
            log_error("file_catalog", type(fallback_error).__name__, str(fallback_error), "Continúa sin catálogo", run_id=run_id)

def main():
    parser = argparse.ArgumentParser(description="Orquestador Maestro del Pipeline ETL Observatorio IA")
    parser.add_argument("--date", type=str, help="Fecha de ejecución (YYYY-MM-DD)", default=datetime.date.today().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    global_logger.info(f">>> INICIANDO PIPELINE UNIFICADO (Fecha Objetivo: {args.date}) <<<")
    run_id = start_pipeline_audit()
    
    try:
        # FASE 1: Extractores
        run_extraction_phase(run_id)
        
        # FASE 2: Ingesta Inmutable
        global_logger.info("=== FASE 2: CARGA RAW A BD ===")
        run_loader()
        
        # FASE 3: Limpieza y Staging
        global_logger.info("=== FASE 3: STAGING ===")
        run_staging_pipeline()
        
        # FASE 4: Métricas de Calidad
        global_logger.info("=== FASE 4: CALIDAD DE DATOS ===")
        run_quality_framework()
        
        # Cierre Exitoso
        end_pipeline_audit(run_id, status="completed")
        global_logger.info(f">>> PIPELINE UNIFICADO COMPLETADO EXITOSAMENTE (Run ID: {run_id}) <<<")
        
    except Exception as e:
        error_str = f"Fallo Crítico: {str(e)}"
        global_logger.error(error_str)
        end_pipeline_audit(run_id, status="failed", error_msg=error_str)

if __name__ == "__main__":
    main()
