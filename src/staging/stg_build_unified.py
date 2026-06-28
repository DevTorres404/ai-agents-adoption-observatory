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

def run_staging_pipeline():
    global_logger.info(">>> INICIANDO PIPELINE DE STAGING (LIMPIEZA E INTEGRACIÓN) <<<")
    
    if not db_connector.engine:
        global_logger.error("Sin conexión a PostgreSQL.")
        return

    try:
        # Extraer registros crudos con metadata de archivo (JOIN)
        query = text("""
            SELECT r.raw_data, f.fuente, f.tipo_fuente, f.id as file_id
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
            key = (fila.fuente, fila.tipo_fuente, fila.file_id)
            if key not in grouped_data:
                grouped_data[key] = []
            grouped_data[key].append(fila.raw_data)
            
        df_consolidado = pd.DataFrame()
        
        # Paso 1: Mapeo y Normalización por Fuente
        for (fuente, tipo_fuente, file_id), records in grouped_data.items():
            df_crudo = pd.DataFrame(records)
            meta = {'fuente': fuente, 'tipo_fuente': tipo_fuente, 'id': file_id}
            
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
        
        # Paso 4: Categorias
        # Motivo: las categorias conectan cada fuente con la dimension estrategica definida en la arquitectura.
        df_consolidado = assign_categories(df_consolidado)
        global_logger.info("Paso 4: Categorías asignadas.")
        
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
            'indice_adopcion', 'indice_innovacion', 'sentimiento_promedio', 'raw_file_id'
        ]
        
        # Motivo: se ajustan nulos y caracteres no validos para que PostgreSQL reciba un dataset tabular consistente.
        df_final = df_consolidado[contrato_columnas].copy()
        text_cols = ['id_origen_registro', 'fuente', 'tipo_fuente', 'plataforma', 'fecha_evento', 'nombre_agente', 'categoria', 'titulo', 'texto', 'url']
        for col in text_cols:
            if col in df_final.columns:
                df_final[col] = df_final[col].map(lambda value: value.replace('\x00', '') if isinstance(value, str) else value)
        df_final = df_final.where(pd.notnull(df_final), None)
        
        # Escribir con to_sql
        # Al usar if_exists='append', dependemos de la clave UNIQUE de la BD para rechazar fallos
        with db_connector.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE staging.stg_actividad_agente_ia RESTART IDENTITY"))
            global_logger.info("Tabla staging.stg_actividad_agente_ia reiniciada para reconstrucciÃ³n reproducible.")

            # Motivo: la insercion fila a fila permite registrar conflictos sin abortar toda la reconstruccion Staging.
            exitos = 0
            fallos = 0
            
            insert_query = text(f"""
                INSERT INTO staging.stg_actividad_agente_ia
                ({','.join(contrato_columnas)})
                VALUES (:{',:'.join(contrato_columnas)})
                ON CONFLICT (fuente, plataforma, id_origen_registro, nombre_agente, fecha_evento) DO NOTHING
            """)
            
            records_to_insert = df_final.to_dict(orient='records')
            
            for rec in records_to_insert:
                try:
                    res = conn.execute(insert_query, rec)
                    if res.rowcount > 0:
                        exitos += 1
                    else:
                        fallos += 1
                except Exception as ex:
                    fallos += 1
                    global_logger.debug(f"Fallo inserción individual: {ex}")
                    
        global_logger.info(f"Carga a BD completada. Insertados: {exitos}. Conflictos o fallos de inserción: {fallos}")
        
        # Exportar evidencia
        evidencia_path = ROOT_DIR / "docs" / "evidencias" / "staging_stats.csv"
        df_final.to_csv(evidencia_path, index=False, encoding='utf-8')
        global_logger.info(f"Data final exportada para evidencia en {evidencia_path}")

    except Exception as e:
        log_error("staging_pipeline", type(e).__name__, str(e), "Pipeline abortado")
        global_logger.error(f"Fallo crítico en Staging: {e}")

if __name__ == "__main__":
    run_staging_pipeline()
