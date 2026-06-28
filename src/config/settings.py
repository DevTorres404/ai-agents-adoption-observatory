import os
from dotenv import load_dotenv
from src.utils.paths import ROOT_DIR

# Cargar variables de entorno desde la raíz del proyecto
env_path = ROOT_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Configuraciones de Base de Datos
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "observatorio_ia")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_HOST = os.getenv("DB_HOST", "localhost")

# String de conexión SQLAlchemy (Dialecto PostgreSQL usando psycopg3)
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Otras configuraciones globales
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
