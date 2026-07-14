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
    **SEMANTIC_DB_COLUMNS,
}

def run_staging_pipeline():
    global_logger.info(">>> INICIANDO PIPELINE DE STAGING (LIMPIEZA E INTEGRACIÓN) <<<")
    
    if not db_connector.engine:
        global_logger.error("Sin conexión a PostgreSQL.")
        return

    try:
        # Extraer registros crudos con metadata de archivo (JOIN)
        query = text("""
            SELECT r.raw_data, f.fuente, f.tipo_fuente, f.id as file_id,
                   f.fecha_carga AS file_load_date
            FROM raw.raw_records r
            JOIN raw.raw_files f ON r.file_id = f.id
        """)
        
        with db_connector.engine.connect() as conn:
            raw_data = conn.execute(query).fetchall()
            
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
            grouped_data[key].append(fila.raw_data)
            
        df_consolidado = pd.DataFrame()
        
        # Paso 1: Mapeo y Normalización por Fuente
        for (fuente, tipo_fuente, file_id, file_load_date), records in grouped_data.items():
            df_crudo = pd.DataFrame(records)
            meta = {
                'fuente': fuente,
                'tipo_fuente': tipo_fuente,
                'id': file_id,
                'fecha_carga': file_load_date,
            }
            
            # Motivo: cada fuente tiene estructura propia; se homologa a un contrato comun antes de integrar.
            df_norm = normalize_dataframe(df_crudo, meta)
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
        
        # Loggear descartes
        if descartados > 0:
            log_error(
                source="staging_pipeline",
                error_type="DuplicateWarning",
                description=f"Se descartaron {descartados} registros durante la deduplicación de Staging.",
                action_taken="Omitidos de la inserción a BD."
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
            'is_imputed_date',
            'dim_nombre_plataforma', 'dim_tipo_plataforma', 'dim_ecosistema',
            'dim_plataforma_metodo', 'dim_nombre_tecnologia',
            'dim_categoria_tecnologia', 'dim_dominio_tecnologico', 'dim_tipo_senal',
            'dim_tecnologia_metodo', 'dim_nombre_comunidad', 'dim_tipo_comunidad',
            'dim_region_comunidad', 'dim_comunidad_metodo'
        ]
        
        # Motivo: se ajustan nulos y caracteres no validos para que PostgreSQL reciba un dataset tabular consistente.
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
        # Escribir con to_sql
        # Al usar if_exists='append', dependemos de la clave UNIQUE de la BD para rechazar fallos
        with db_connector.engine.begin() as conn:
            # Compatibilidad con instalaciones existentes que no vuelven a
            # ejecutar 03_staging_tables.sql antes de reconstruir Staging.
            for column, sql_type in STAGING_COMPAT_DB_COLUMNS.items():
                conn.execute(text(
                    f"ALTER TABLE staging.stg_actividad_agente_ia "
                    f"ADD COLUMN IF NOT EXISTS {column} {sql_type}"
                ))
            # Algunos IDs de origen son URLs completas de más de 255 caracteres.
            # TEXT evita truncamiento y conserva la identidad real del registro.
            conn.execute(text(
                "ALTER TABLE staging.stg_actividad_agente_ia "
                "ALTER COLUMN id_origen_registro TYPE TEXT"
            ))
            conn.execute(text("TRUNCATE TABLE staging.stg_actividad_agente_ia RESTART IDENTITY"))
            global_logger.info("Tabla staging.stg_actividad_agente_ia reiniciada para reconstrucciÃ³n reproducible.")

            # Motivo: los lotes reducen round-trips. ON CONFLICT sin columnas
            # funciona tanto con la clave histórica de 5 campos como con el
            # contrato actual de 4 campos.
            exitos = 0
            
            insert_query = text(f"""
                INSERT INTO staging.stg_actividad_agente_ia
                ({','.join(contrato_columnas)})
                VALUES (:{',:'.join(contrato_columnas)})
                ON CONFLICT DO NOTHING
            """)
            
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

            exitos = conn.execute(text(
                "SELECT COUNT(*) FROM staging.stg_actividad_agente_ia"
            )).scalar_one()
            conflictos = len(records_to_insert) - exitos

        global_logger.info(f"Carga a BD completada. Insertados: {exitos}. Conflictos omitidos: {conflictos}")
        
        # Exportar evidencia
        evidencia_path = ROOT_DIR / "docs" / "evidencias" / "staging_stats.csv"
        df_final.to_csv(evidencia_path, index=False, encoding='utf-8')
        global_logger.info(f"Data final exportada para evidencia en {evidencia_path}")

    except Exception as e:
        log_error("staging_pipeline", type(e).__name__, str(e), "Pipeline abortado")
        global_logger.error(f"Fallo crítico en Staging: {e}")
        raise

if __name__ == "__main__":
    run_staging_pipeline()
