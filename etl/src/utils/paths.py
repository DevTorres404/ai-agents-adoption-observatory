from pathlib import Path

# Raíz del proyecto (Asumiendo que paths.py está en src/utils/)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# Directorios principales
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
LOGS_DIR = ROOT_DIR / "logs"
SQL_DIR = ROOT_DIR / "sql"

# Crear los directorios dinámicamente si no existen
def ensure_directories():
    for directory in [DATA_DIR, RAW_DIR, STAGING_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

ensure_directories()
