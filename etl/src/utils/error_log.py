import csv
import datetime
from sqlalchemy import text
from src.utils.paths import LOGS_DIR
from src.utils.db import db_connector
from src.utils.logger import global_logger

def log_error(source, error_type, description, action_taken, run_id=None):
    """
    Registra errores en logs/pipeline_errors.csv y opcionalmente en audit.pipeline_errors (BD).
    """
    log_file = LOGS_DIR / "pipeline_errors.csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Escribir a CSV (Siempre)
    try:
        file_exists = log_file.exists()
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Run_ID", "Fuente", "Tipo_Error", "Descripcion", "Accion_Tomada"])
            writer.writerow([timestamp, run_id, source, error_type, description, action_taken])
    except Exception as e:
        global_logger.error(f"Fallo al escribir el error_log.csv: {e}")

    # Escribir a PostgreSQL (Si la BD está viva y hay un run_id)
    if db_connector.engine and run_id:
        try:
            with db_connector.engine.begin() as conn:
                query = text("""
                    INSERT INTO audit.pipeline_errors 
                    (run_id, error_timestamp, source, error_type, description, action_taken)
                    VALUES (:run_id, :timestamp, :source, :type, :desc, :action)
                """)
                conn.execute(query, {
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "source": source,
                    "type": error_type,
                    "desc": description,
                    "action": action_taken
                })
        except Exception as e:
            global_logger.error(f"Fallo al registrar error en la base de datos audit.pipeline_errors: {e}")
