import pandas as pd
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.paths import ROOT_DIR
from src.quality.quality_checks import (
    get_casting_report,
    get_dedup_report,
    get_homologation_map,
    get_nulls_matrix,
    get_overall_metrics,
    get_quality_issue_breakdown,
    get_staging_contract_report,
)

def run_quality_framework():
    global_logger.info(">>> INICIANDO FRAMEWORK DE CALIDAD DE DATOS (E3) <<<")
    
    if not db_connector.engine:
        global_logger.error("No hay conexión a la base de datos.")
        return

    # Extraer métricas
    summary = get_overall_metrics()
    nulls = get_nulls_matrix()
    dedup = get_dedup_report()
    homologation = get_homologation_map()
    quality_breakdown = get_quality_issue_breakdown()
    casting = get_casting_report()
    staging_contract = get_staging_contract_report()
    
    # 1. Insertar en BD
    try:
        with db_connector.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit.quality_issue_breakdown (
                    id SERIAL PRIMARY KEY,
                    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name VARCHAR(120),
                    metric_value INTEGER,
                    evidence_basis TEXT,
                    academic_interpretation TEXT
                )
            """))

            # Summary
            conn.execute(text("""
                INSERT INTO audit.quality_summary 
                (total_raw_records, total_staging_records, completion_rate, total_duplicates_removed, total_nulls_removed, overall_error_rate)
                VALUES (:total_raw_records, :total_staging_records, :completion_rate, :total_duplicates_removed, :total_nulls_removed, :overall_error_rate)
            """), summary)
            
            # Nulls
            for n in nulls:
                conn.execute(text("""
                    INSERT INTO audit.nulls_matrix 
                    (source, column_name, null_count, total_count, null_percentage, strategy_applied)
                    VALUES (:source, :column_name, :null_count, :total_count, :null_percentage, :strategy_applied)
                """), n)
                
            # Dedup
            for d in dedup:
                conn.execute(text("""
                    INSERT INTO audit.dedup_report 
                    (source, total_detected, total_removed, total_kept)
                    VALUES (:source, :total_detected, :total_removed, :total_kept)
                """), d)
                
            # Homologation (Upsert)
            for h in homologation:
                conn.execute(text("""
                    INSERT INTO audit.homologation_map (source, source_field, staging_field, transformation_rule)
                    VALUES (:source, :source_field, :staging_field, :transformation_rule)
                    ON CONFLICT (source, source_field, staging_field) DO NOTHING
                """), h)

            for c in casting:
                conn.execute(text("""
                    INSERT INTO audit.casting_report
                    (source, field_name, target_type, failed_conversions, example_before, example_after)
                    VALUES (:source, :field_name, :target_type, :failed_conversions, :example_before, :example_after)
                """), c)

            for q in quality_breakdown:
                conn.execute(text("""
                    INSERT INTO audit.quality_issue_breakdown
                    (metric_name, metric_value, evidence_basis, academic_interpretation)
                    VALUES (:metric_name, :metric_value, :evidence_basis, :academic_interpretation)
                """), q)
                
    except Exception as e:
        global_logger.error(f"Fallo al guardar métricas en la base de datos: {e}")
        
    # 2. Exportar CSVs para evidencias (Requisito Académico)
    docs_dir = ROOT_DIR / "docs" / "evidencias"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    pd.DataFrame([summary]).to_csv(docs_dir / "quality_summary.csv", index=False)
    pd.DataFrame(nulls).to_csv(docs_dir / "nulls_matrix.csv", index=False)
    pd.DataFrame(dedup).to_csv(docs_dir / "dedup_report.csv", index=False)
    pd.DataFrame(homologation).to_csv(docs_dir / "homologation_map.csv", index=False)
    pd.DataFrame(quality_breakdown).to_csv(docs_dir / "quality_issue_breakdown.csv", index=False)
    pd.DataFrame(casting).to_csv(docs_dir / "casting_report.csv", index=False)
    pd.DataFrame(staging_contract).to_csv(docs_dir / "staging_contract_columns.csv", index=False)
    
    # 3. Resumen en Consola
    print("\n" + "="*50)
    print(" REPORTE FINAL DE MÉTRICAS DE CALIDAD (E3)")
    print("="*50)
    print(f"Total registros crudos procesados (Raw): {summary['total_raw_records']}")
    print(f"Total registros consolidados aptos (Staging): {summary['total_staging_records']}")
    print(f"Tasa de completitud general: {summary['completion_rate']}%")
    print(f"Registros depurados por duplicados reales: {summary['total_duplicates_removed']}")
    print(f"Registros eliminados por nulos críticos: {summary['total_nulls_removed']}")
    print(f"Tasa de error (merma) promedio: {summary['overall_error_rate']}%")
    print("="*50 + "\n")
    
    global_logger.info(f"Métricas insertadas en BD y exportadas en CSV a {docs_dir.relative_to(ROOT_DIR)}")

if __name__ == "__main__":
    run_quality_framework()
