import os
import hashlib
import json
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from src.utils.paths import RAW_DIR, ROOT_DIR
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.error_log import log_error

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_metadata(filepath):
    rel_path = filepath.relative_to(RAW_DIR)
    partes = rel_path.parts
    fuente = partes[0] if len(partes) > 1 else "desconocido"
    tipo_fuente = fuente
    
    cantidad_registros = 0
    cantidad_columnas = 0
    records = []
    
    try:
        if filepath.suffix == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if isinstance(data, dict) and 'items' in data:
                records = data['items']
            elif isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = [data]
                
            cantidad_registros = len(records)
            cantidad_columnas = len(records[0].keys()) if cantidad_registros > 0 and isinstance(records[0], dict) else 0

        elif filepath.suffix in ['.csv', '.xlsx', '.xls']:
            if filepath.suffix == '.csv':
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
                
            # Limpiar NaN/NaT para PostgreSQL JSONB
            df = df.where(pd.notnull(df), None)
            # Convertir fechas a string ISO
            for col in df.select_dtypes(include=['datetime64']).columns:
                df[col] = df[col].dt.strftime('%Y-%m-%dT%H:%M:%S')
                
            cantidad_registros = len(df)
            cantidad_columnas = len(df.columns)
            records = df.to_dict(orient="records")
            
    except Exception as e:
        global_logger.warning(f"No se pudo procesar estructuralmente {filepath.name}: {e}")
        
    return {
        "fuente": fuente,
        "tipo_fuente": tipo_fuente,
        "ruta_relativa": str(rel_path).replace("\\", "/"),
        "nombre_archivo": filepath.name,
        "tamano_bytes": filepath.stat().st_size,
        "cantidad_registros": cantidad_registros,
        "cantidad_columnas": cantidad_columnas,
        "records": records 
    }

def run_loader():
    global_logger.info(">>> INICIANDO CARGA RAW A POSTGRESQL <<<")
    
    if not db_connector.engine:
        global_logger.error("No hay conexión a BD. Saliendo...")
        return
        
    archivos_procesados = 0
    archivos_ignorados = 0
    inventario = []

    for filepath in RAW_DIR.rglob("*"):
        if filepath.is_file() and filepath.suffix in ['.json', '.csv', '.xlsx', '.xls']:
            file_hash = calculate_sha256(filepath)
            
            try:
                with db_connector.engine.connect() as conn:
                    query_check = text("SELECT id FROM raw.raw_files WHERE hash_sha256 = :hash")
                    result = conn.execute(query_check, {"hash": file_hash}).fetchone()
                    
                    if result:
                        archivos_ignorados += 1
                        global_logger.info(f"Omitido (Duplicado): {filepath.name}")
                        continue
                    
                    meta = extract_metadata(filepath)
                    records_to_insert = meta.pop("records", [])
                    meta["hash_sha256"] = file_hash
                    
                    query_insert_file = text("""
                        INSERT INTO raw.raw_files 
                        (fuente, tipo_fuente, ruta_relativa, nombre_archivo, cantidad_registros, cantidad_columnas, tamano_bytes, hash_sha256)
                        VALUES (:fuente, :tipo_fuente, :ruta_relativa, :nombre_archivo, :cantidad_registros, :cantidad_columnas, :tamano_bytes, :hash_sha256)
                        RETURNING id;
                    """)
                    file_id = conn.execute(query_insert_file, meta).scalar()
                    conn.commit()
                    
                    if records_to_insert:
                        query_insert_record = text("""
                            INSERT INTO raw.raw_records (file_id, raw_data)
                            VALUES (:file_id, :raw_data)
                        """)
                        
                        for record in records_to_insert:
                            conn.execute(query_insert_record, {
                                "file_id": file_id,
                                "raw_data": json.dumps(record, ensure_ascii=False)
                            })
                        conn.commit()

                    
                    archivos_procesados += 1
                    inventario.append(meta)
                    global_logger.info(f"Cargado exitosamente: {filepath.name} ({meta['cantidad_registros']} registros)")
                    
            except Exception as e:
                log_error("load_raw_to_db", type(e).__name__, str(e), f"Fallo al procesar {filepath.name}")
                global_logger.error(f"Fallo al procesar {filepath.name}: {e}")

    global_logger.info(f"Carga completada. Nuevos: {archivos_procesados}. Ignorados: {archivos_ignorados}")
    
    # Exportar inventario de archivos nuevos de la corrida
    if inventario:
        docs_dir = ROOT_DIR / "docs" / "evidencias"
        docs_dir.mkdir(parents=True, exist_ok=True)
        inventario_df = pd.DataFrame(inventario)
        inventario_file = docs_dir / "inventario_raw.csv"
        inventario_df.to_csv(inventario_file, index=False)
        global_logger.info(f"Inventario CSV exportado a {inventario_file.relative_to(ROOT_DIR)}")

    export_full_raw_inventory()


def export_full_raw_inventory():
    """
    Exporta el inventario completo de Raw desde PostgreSQL. Esta evidencia representa
    el universo real cargado en BD, incluyendo archivos de corridas previas.
    """
    if not db_connector.engine:
        return

    docs_dir = ROOT_DIR / "docs" / "evidencias"
    docs_dir.mkdir(parents=True, exist_ok=True)
    query = text("""
        SELECT
            f.id AS raw_file_id,
            f.fuente,
            f.tipo_fuente,
            f.ruta_relativa,
            f.nombre_archivo,
            f.cantidad_registros AS declared_records,
            COUNT(r.id) AS loaded_records,
            f.cantidad_columnas,
            f.tamano_bytes,
            f.hash_sha256,
            f.fecha_carga
        FROM raw.raw_files f
        LEFT JOIN raw.raw_records r ON r.file_id = f.id
        GROUP BY f.id
        ORDER BY f.id
    """)

    try:
        with db_connector.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        full_inventory = pd.DataFrame(rows)
        out_file = docs_dir / "inventario_raw_completo.csv"
        full_inventory.to_csv(out_file, index=False)
        global_logger.info(f"Inventario Raw completo exportado a {out_file.relative_to(ROOT_DIR)}")
    except Exception as e:
        log_error("load_raw_to_db", type(e).__name__, str(e), "No se pudo exportar inventario Raw completo")

if __name__ == "__main__":
    run_loader()
