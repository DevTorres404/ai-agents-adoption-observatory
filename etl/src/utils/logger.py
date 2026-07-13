import logging
from src.utils.paths import LOGS_DIR

def setup_logger(name="pipeline_logger"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Evitar duplicar handlers si se llama múltiples veces
    if not logger.handlers:
        # Formateador estándar
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Archivo
        file_handler = logging.FileHandler(LOGS_DIR / "pipeline_run.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

global_logger = setup_logger()
