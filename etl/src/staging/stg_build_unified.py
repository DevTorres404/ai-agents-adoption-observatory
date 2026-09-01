import json
import pandas as pd
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.error_log import log_error
from src.utils.paths import ROOT_DIR

# Importar los módulos del pipeline Staging
from src.staging.stg_normalize_columns import normalize_dataframe
from src.staging.stg_dates import parse_dates
from src.staging.stg_agents import extract_agent
from src.staging.stg_categories import assign_categories
from src.staging.stg_dedup import deduplicate_staging
from src.staging.stg_llm_enrichment import enrich_with_llm
from src.staging.stg_semantic_dimensions import enrich_semantic_dimensions


SEMANTIC_DB_COLUMNS = {
    "dim_nombre_plataforma": "VARCHAR(100)",
    "dim_tipo_plataforma": "VARCHAR(100)",
    "dim_ecosistema": "VARCHAR(100)",
    "dim_plataforma_metodo": "VARCHAR(50)",
    "dim_nombre_tecnologia": "VARCHAR(120)",
    "dim_categoria_tecnologia": "VARCHAR(100)",
    "dim_dominio_tecnologico": "VARCHAR(120)",
    "dim_tipo_senal": "VARCHAR(100)",
    "dim_tecnologia_metodo": "VARCHAR(50)",
    "dim_nombre_comunidad": "VARCHAR(120)",
    "dim_tipo_comunidad": "VARCHAR(100)",
    "dim_region_comunidad": "VARCHAR(100)",
    "dim_comunidad_metodo": "VARCHAR(50)",
}

STAGING_COMPAT_DB_COLUMNS = {
    "is_imputed_date": "BOOLEAN DEFAULT FALSE",
    "raw_record_id": "INTEGER REFERENCES raw.raw_records(id)",
    "transformation_version": "VARCHAR(50)",
    **SEMANTIC_DB_COLUMNS,
}

TRANSFORMATION_VERSION = "staging-v1"
BUSINESS_KEY = ["fuente", "plataforma", "id_origen_registro", "nombre_agente"]


def plan_staging_files(
    available_file_ids,
    processed_file_ids,
    stored_versions,
    rebuild=False,
):
    """Selects a deterministic delta and prevents implicit version rebuilds."""
    available = sorted({int(file_id) for file_id in available_file_ids})
    versions = {version for version in stored_versions if version}
    incompatible = versions - {TRANSFORMATION_VERSION}
    if incompatible and not rebuild:
        raise RuntimeError(
            "Staging transformation version changed; run with explicit rebuild mode "
            f"(stored={sorted(incompatible)}, current={TRANSFORMATION_VERSION})."
        )
    if rebuild:
        return available
    processed = {int(file_id) for file_id in processed_file_ids}
    return [file_id for file_id in available if file_id not in processed]


def build_staging_upsert_sql(columns):
    update_columns = [column for column in columns if column not in BUSINESS_KEY]
    assignments = [f"{column} = EXCLUDED.{column}" for column in update_columns]
    assignments.append("fecha_carga = CURRENT_TIMESTAMP")
    return f"""
        INSERT INTO staging.stg_actividad_agente_ia
        ({','.join(columns)})
        VALUES (:{',:'.join(columns)})
        ON CONFLICT ({','.join(BUSINESS_KEY)}) DO UPDATE SET
            {','.join(assignments)}
        WHERE (
            COALESCE(EXCLUDED.fecha_evento, DATE '-infinity'),
            COALESCE(EXCLUDED.raw_file_id, 0),
            COALESCE(EXCLUDED.raw_record_id, 0)
        ) > (
            COALESCE(staging.stg_actividad_agente_ia.fecha_evento, DATE '-infinity'),
            COALESCE(staging.stg_actividad_agente_ia.raw_file_id, 0),
            COALESCE(staging.stg_actividad_agente_ia.raw_record_id, 0)
        )
    """


def _ensure_staging_schema(conn):
    for column, sql_type in STAGING_COMPAT_DB_COLUMNS.items():
        conn.execute(text(
            f"ALTER TABLE staging.stg_actividad_agente_ia "
            f"ADD COLUMN IF NOT EXISTS {column} {sql_type}"
        ))
    conn.execute(text(
        "ALTER TABLE staging.stg_actividad_agente_ia "
        "ALTER COLUMN id_origen_registro TYPE TEXT"
    ))
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_staging_activity_business_key
        ON staging.stg_actividad_agente_ia
           (fuente, plataforma, id_origen_registro, nombre_agente)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS staging.processed_files (
            file_id INTEGER PRIMARY KEY REFERENCES raw.raw_files(id) ON DELETE CASCADE,
            transformation_version VARCHAR(50) NOT NULL,
            processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            run_id INTEGER REFERENCES audit.pipeline_runs(run_id),
            records_processed INTEGER NOT NULL DEFAULT 0
        )
    """))


def run_staging_pipeline(run_id=None, rebuild=False):
    global_logger.info(">>> INICIANDO PIPELINE DE STAGING (LIMPIEZA E INTEGRACIÓN) <<<")
    
    if not db_connector.engine:
        global_logger.error("Sin conexión a PostgreSQL.")
        return

    try:
        with db_connector.engine.begin() as conn:
            _ensure_staging_schema(conn)
            available_file_ids = conn.execute(text("""
                SELECT DISTINCT f.id
                FROM raw.raw_files f
                JOIN raw.raw_records r ON r.file_id = f.id
                ORDER BY f.id
            """)).scalars().all()
            processed_rows = conn.execute(text("""
                SELECT file_id, transformation_version
                FROM staging.processed_files
            """)).fetchall()

        file_ids = plan_staging_files(
            available_file_ids=available_file_ids,
            processed_file_ids=[row.file_id for row in processed_rows],
            stored_versions=[row.transformation_version for row in processed_rows],
            rebuild=rebuild,
        )
        if not file_ids:
            if rebuild:
                with db_connector.engine.begin() as conn:
                    _ensure_staging_schema(conn)
                    conn.execute(text(
                        "TRUNCATE TABLE staging.stg_actividad_agente_ia RESTART IDENTITY"
                    ))
                    conn.execute(text("DELETE FROM staging.processed_files"))
                global_logger.info(
                    "Staging reconstruido vacío mediante modo rebuild explícito."
                )
            else:
                global_logger.info(
                    "Staging incremental sin archivos pendientes "
                    f"(version={TRANSFORMATION_VERSION})."
                )
            return {"processed_files": 0, "processed_records": 0, "rebuild": rebuild}

        query = text("""
            SELECT r.id AS raw_record_id, r.raw_data, f.fuente,
                   f.tipo_fuente, f.id AS file_id,
                   f.fecha_carga AS file_load_date
            FROM raw.raw_records r
            JOIN raw.raw_files f ON r.file_id = f.id
            WHERE f.id = ANY(:file_ids)
            ORDER BY f.id, r.id
        """)

        with db_connector.engine.connect() as conn:
            raw_data = conn.execute(query, {"file_ids": file_ids}).fetchall()
            
        if not raw_data:
            global_logger.warning("No hay registros en raw.raw_records para procesar.")
            return

        global_logger.info(f"Leídos {len(raw_data)} registros crudos desde BD.")
        
        # Procesaremos agrupando por archivo para optimizar
        grouped_data = {}
        for fila in raw_data:
            key = (fila.fuente, fila.tipo_fuente, fila.file_id, fila.file_load_date)
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append((fila.raw_record_id, fila.raw_data))
            
        df_consolidado = pd.DataFrame()
        
        # Paso 1: Mapeo y Normalización por Fuente
        for (fuente, tipo_fuente, file_id, file_load_date), records in grouped_data.items():
            raw_record_ids, raw_payloads = zip(*records)
            df_crudo = pd.DataFrame(raw_payloads)
            meta = {
                'fuente': fuente,
                'tipo_fuente': tipo_fuente,
                'id': file_id,
                'fecha_carga': file_load_date,
            }
            
            # Motivo: cada fuente tiene estructura propia; se homologa a un contrato comun antes de integrar.
            df_norm = normalize_dataframe(df_crudo, meta)
            df_norm['raw_record_id'] = list(raw_record_ids)
            df_consolidado = pd.concat([df_consolidado, df_norm], ignore_index=True)
            
        global_logger.info("Paso 1: Normalización de columnas completada.")
        
        # Paso 2: Fechas
        # Motivo: Staging trabaja a granularidad diaria para soportar analisis historico y deduplicacion.
        df_consolidado = parse_dates(df_consolidado)
        global_logger.info("Paso 2: Fechas estandarizadas a YYYY-MM-DD.")
        
        # Paso 3: Agentes
        # Motivo: la homologacion por regex agrupa alias de una misma herramienta bajo un nombre analitico.
        df_consolidado = extract_agent(df_consolidado)
        global_logger.info("Paso 3: Identidad de Agentes procesada.")
        
        # Paso 3.1: Exclusión de ruido
        # Motivo: El usuario definió descartar cualquier mención que no coincida con los agentes explícitamente autorizados.
        filas_antes = len(df_consolidado)
        df_consolidado = df_consolidado[df_consolidado['nombre_agente'] != 'Otro Agente IA']
        global_logger.info(f"Paso 3.1: Exclusión de ruido aplicada. Descartados {filas_antes - len(df_consolidado)} registros genéricos.")
        
        # Paso 4: Categorias
        # Motivo: las categorias conectan cada fuente con la dimension estrategica definida en la arquitectura.
        df_consolidado = assign_categories(df_consolidado)
        global_logger.info("Paso 4: Categorías asignadas.")
        
        # Paso 4.5: Enriquecimiento Semántico (LLM)
        df_consolidado = enrich_with_llm(df_consolidado)

        # Paso 4.6: Dimensiones semánticas deterministas
        # Motivo: Gold recibe claves de negocio explícitas; nunca reutiliza
        # categoria o plataforma como sustitutos de tecnología/comunidad.
        df_consolidado = enrich_semantic_dimensions(df_consolidado)
        global_logger.info("Paso 4.6: Plataforma, tecnología y comunidad enriquecidas con reglas trazables.")
        
        # Paso 5: Deduplicacion
        # Motivo: se eliminan repeticiones analiticas sin alterar la capa Raw, que permanece como evidencia original.
        df_consolidado, descartados = deduplicate_staging(df_consolidado)
        global_logger.info(f"Paso 5: Deduplicación completada. Se descartaron {descartados} registros.")
        
        # Deduplication is an intentional historical consolidation, not an error.
        if descartados > 0:
            global_logger.info(
                f"Deduplicación histórica: {descartados} registros consolidados; "
                "no se registran como errores de carga."
            )
            
        # Paso 6: Inserción en Staging
        # Asegurarnos de que las columnas coincidan con el contrato exacto
        contrato_columnas = [
            'id_origen_registro', 'fuente', 'tipo_fuente', 'plataforma', 
            'fecha_evento', 'nombre_agente', 'categoria', 'titulo', 'texto', 'url',
            'cantidad_menciones', 'cantidad_interacciones', 'score_popularidad',
            'stars_github', 'forks_github', 'issues_abiertos', 'releases',
            'indice_adopcion', 'indice_innovacion', 'sentimiento_promedio',
            'llm_entorno_uso', 'llm_tipo_integracion', 'llm_categoria_tecnologia',
            'llm_capacidades', 'llm_comunidad_tipo', 'llm_confianza', 'raw_file_id',
            'raw_record_id', 'transformation_version',
            'is_imputed_date',
            'dim_nombre_plataforma', 'dim_tipo_plataforma', 'dim_ecosistema',
            'dim_plataforma_metodo', 'dim_nombre_tecnologia',
            'dim_categoria_tecnologia', 'dim_dominio_tecnologico', 'dim_tipo_senal',
            'dim_tecnologia_metodo', 'dim_nombre_comunidad', 'dim_tipo_comunidad',
            'dim_region_comunidad', 'dim_comunidad_metodo'
        ]
        
        # Motivo: se ajustan nulos y caracteres no validos para que PostgreSQL reciba un dataset tabular consistente.
        df_consolidado['transformation_version'] = TRANSFORMATION_VERSION
        df_final = df_consolidado[contrato_columnas].copy()
        text_cols = [
            'id_origen_registro', 'fuente', 'tipo_fuente', 'plataforma',
            'fecha_evento', 'nombre_agente', 'categoria', 'titulo', 'texto', 'url',
            'llm_entorno_uso', 'llm_tipo_integracion', 'llm_categoria_tecnologia',
            'llm_capacidades', 'llm_comunidad_tipo', *SEMANTIC_DB_COLUMNS.keys()
        ]
        for col in text_cols:
            if col in df_final.columns:
                df_final[col] = df_final[col].map(lambda value: value.replace('\x00', '') if isinstance(value, str) else value)
        df_final = df_final.where(pd.notnull(df_final), None)
        
        # Prevenir desbordamiento de VARCHAR(500) que aborta la transaccion
        if 'url' in df_final.columns:
            df_final['url'] = df_final['url'].apply(lambda x: str(x)[:500] if pd.notnull(x) else None)
        with db_connector.engine.begin() as conn:
            _ensure_staging_schema(conn)
            if rebuild:
                conn.execute(text("TRUNCATE TABLE staging.stg_actividad_agente_ia RESTART IDENTITY"))
                conn.execute(text("DELETE FROM staging.processed_files"))
                global_logger.info(
                    "Staging reiniciado mediante modo rebuild explícito "
                    f"(version={TRANSFORMATION_VERSION})."
                )

            insert_query = text(build_staging_upsert_sql(contrato_columnas))
            
            records_to_insert = df_final.to_dict(orient='records')

            batch_size = 1000
            for start in range(0, len(records_to_insert), batch_size):
                batch = records_to_insert[start:start + batch_size]
                try:
                    conn.execute(insert_query, batch)
                except Exception as ex:
                    raise RuntimeError(
                        f"Fallo insertando lote Staging {start}-{start + len(batch) - 1}: {ex}"
                    ) from ex

            staged_total = conn.execute(text(
                "SELECT COUNT(*) FROM staging.stg_actividad_agente_ia"
            )).scalar_one()
            per_file_counts = df_final.groupby('raw_file_id').size().to_dict()
            processing_rows = [
                {
                    "file_id": file_id,
                    "transformation_version": TRANSFORMATION_VERSION,
                    "run_id": run_id,
                    "records_processed": int(per_file_counts.get(file_id, 0)),
                }
                for file_id in file_ids
            ]
            conn.execute(text("""
                INSERT INTO staging.processed_files
                    (file_id, transformation_version, run_id, records_processed)
                VALUES
                    (:file_id, :transformation_version, :run_id, :records_processed)
                ON CONFLICT (file_id) DO UPDATE SET
                    transformation_version = EXCLUDED.transformation_version,
                    processed_at = CURRENT_TIMESTAMP,
                    run_id = EXCLUDED.run_id,
                    records_processed = EXCLUDED.records_processed
            """), processing_rows)

        global_logger.info(
            f"Carga Staging completada. Archivos procesados: {len(file_ids)}. "
            f"Candidatos: {len(records_to_insert)}. Total materializado: {staged_total}."
        )
        
        # Exportar evidencia
        evidencia_path = ROOT_DIR / "docs" / "evidencias" / "staging_stats.csv"
        df_final.to_csv(evidencia_path, index=False, encoding='utf-8')
        global_logger.info(f"Data final exportada para evidencia en {evidencia_path}")
        return {
            "processed_files": len(file_ids),
            "processed_records": len(records_to_insert),
            "staged_total": staged_total,
            "rebuild": rebuild,
            "transformation_version": TRANSFORMATION_VERSION,
        }

    except Exception as e:
        log_error("staging_pipeline", type(e).__name__, str(e), "Pipeline abortado")
        global_logger.error(f"Fallo crítico en Staging: {e}")
        raise

if __name__ == "__main__":
    run_staging_pipeline()
