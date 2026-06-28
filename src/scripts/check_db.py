from src.utils.db import db_connector
from src.utils.logger import global_logger
from sqlalchemy import text

def check():
    global_logger.info(">>> Verificando conexión a PostgreSQL...")
    if db_connector.test_connection():
        global_logger.info("PostgreSQL local corriendo en Docker está listo para recibir datos.")
        
        # Validar si las tablas audit están creadas
        try:
            with db_connector.engine.connect() as conn:
                result = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'audit';"))
                count = result.scalar()
                if count > 0:
                    global_logger.info(f"Se encontraron {count} tablas en el esquema 'audit'.")
                else:
                    global_logger.warning("No se encontraron tablas en el esquema 'audit'.")
        except Exception as e:
            global_logger.error(f"Error comprobando esquemas: {e}")
    else:
        global_logger.error("No se pudo conectar a la base de datos.")

if __name__ == "__main__":
    check()
