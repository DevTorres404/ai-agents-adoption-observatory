import datetime
import json
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR, ROOT_DIR


class AgenteIA(BaseModel):
    id: str = Field(..., min_length=1)
    nombre_oficial: str = Field(..., min_length=2)
    empresa: str = Field(...)
    categoria: str = Field(...)
    estado: str = Field(...)
    es_open_source: bool
    anio_lanzamiento: Optional[int] = Field(None, ge=1950, le=2030)


def extract_and_validate_catalog():
    """Lee el maestro local, valida Pydantic y guarda un Raw inmutable."""
    global_logger.info("Iniciando validacion Pydantic del catalogo maestro...")
    source_path = ROOT_DIR / "data" / "manual" / "maestro_agentes.json"

    if not source_path.exists():
        global_logger.warning("Archivo maestro_agentes.json no encontrado.")
        log_source_execution("catalogo", "failed", 0, None, str(source_path), notes="Archivo no encontrado")
        return

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        valid_records = []
        for index, item in enumerate(data):
            try:
                agente_valido = AgenteIA(**item)
                valid_records.append(agente_valido.model_dump())
            except ValidationError as exc:
                log_error("file_catalog", "PydanticValidationError", f"Fila {index} invalida: {exc}", "Registro omitido")

        global_logger.info(f"Catalogo validado: {len(valid_records)}/{len(data)} registros correctos.")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_dir = RAW_DIR / "archivos" / "catalogo"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"maestro_agentes_{timestamp}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(valid_records, f, ensure_ascii=False, indent=2)

        log_source_execution("catalogo", "success", len(valid_records), None, str(source_path), out_path)
        global_logger.info(f"Catalogo guardado en Raw: {out_path.name}")

    except Exception as exc:
        log_error("file_catalog", type(exc).__name__, str(exc), "Abortado extractor de archivo")
        log_source_execution("catalogo", "failed", 0, None, str(source_path), notes=str(exc))
        global_logger.error(f"Fallo critico en validacion de catalogo: {exc}")


if __name__ == "__main__":
    extract_and_validate_catalog()
