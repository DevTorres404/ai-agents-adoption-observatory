import datetime
import json

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR, ROOT_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"
SOURCE_PATH = ROOT_DIR / "data" / "encuesta" / "encuesta.json"


FIELD_MAP = {
    "Marca temporal": "timestamp_respuesta",
    "Perfil del participante": "perfil_participante",
    "Â¿Usas actualmente agentes o herramientas de IA para programar?": "usa_ia",
    "¿Usas actualmente agentes o herramientas de IA para programar?": "usa_ia",
    "Herramienta de IA que mas utilizas para programar": "herramienta_principal",
    "Frecuencia de uso de herramientas de IA en programacion": "frecuencia_uso_ia",
    "Actividad principal donde usas o usarias IA": "actividad_uso_ia",
    "Â¿Cuanto mejora tu productividad el uso de IA al programar?": "mejora_productividad",
    "¿Cuanto mejora tu productividad el uso de IA al programar?": "mejora_productividad",
    "Principal barrera para adoptar agentes de IA": "barrera_adopcion",
}


def _normalize_response(row):
    normalized = {}
    for source_field, target_field in FIELD_MAP.items():
        if source_field in row:
            normalized[target_field] = row.get(source_field)

    normalized["fuente_original"] = "Google Forms"
    normalized["instrumento"] = "Encuesta UPSE sobre adopcion de agentes de IA"
    return normalized


def extract_google_forms_survey():
    """
    Convierte la exportacion JSON de Google Forms en un archivo Raw inmutable.
    No simula respuestas: solo normaliza encabezados para facilitar Staging.
    """
    global_logger.info("Iniciando extraccion local de encuesta Google Forms...")

    if not SOURCE_PATH.exists():
        message = f"No existe el archivo fuente: {SOURCE_PATH}"
        log_error("google_forms_survey", "FileNotFoundError", message, "Extractor omitido")
        log_source_execution("fuente_propia", "failed", 0, None, str(SOURCE_PATH), notes=message)
        return

    try:
        with open(SOURCE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("encuesta.json debe contener una lista de respuestas")

        records = [_normalize_response(row) for row in data if isinstance(row, dict)]
        date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        out_dir = RAW_DIR / "fuente_propia" / "fuente_propia"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"fuente_propia_{date_stamp}.json"

        payload = {
            "metadata": {
                "source": "fuente_propia",
                "source_system": "Google Forms",
                "date_range_start": SOURCE_START_DATE,
                "date_range_end": SOURCE_END_DATE,
                "records_extracted": len(records),
                "extracted_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "source_file": str(SOURCE_PATH.relative_to(ROOT_DIR)).replace("\\", "/"),
            },
            "items": records,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        log_source_execution(
            "fuente_propia",
            "success",
            len(records),
            None,
            str(SOURCE_PATH),
            out_path,
            notes="Encuesta Google Forms normalizada desde data/encuesta/encuesta.json",
        )
        global_logger.info(f"Encuesta Google Forms guardada en Raw: {out_path.name}")

    except Exception as exc:
        log_error("google_forms_survey", type(exc).__name__, str(exc), "Extractor abortado")
        log_source_execution("fuente_propia", "failed", 0, None, str(SOURCE_PATH), notes=str(exc))
        global_logger.error(f"Fallo en extractor Google Forms: {exc}")


if __name__ == "__main__":
    extract_google_forms_survey()
