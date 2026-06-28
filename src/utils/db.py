from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.settings import DATABASE_URL
from src.utils.logger import global_logger

class DatabaseConnector:
    """
    Abstracción de conexión a la Base de Datos usando SQLAlchemy.
    """
    def __init__(self):
        try:
            self.engine = create_engine(DATABASE_URL, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        except Exception as e:
            global_logger.error(f"Fallo al inicializar el engine de base de datos: {e}")
            self.engine = None

    def get_session(self):
        """Generador de sesiones para usarse con context managers"""
        if not self.engine:
            return None
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def test_connection(self):
        """Prueba de ping básica a PostgreSQL"""
        if not self.engine:
            return False
            
        try:
            with self.engine.connect() as connection:
                global_logger.info("Conexión a PostgreSQL establecida exitosamente.")
                return True
        except Exception as e:
            global_logger.error(f"No se pudo conectar a PostgreSQL: {e}")
            return False

# Instancia global para ser importada
db_connector = DatabaseConnector()
