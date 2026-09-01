import datetime
import json
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution, raw_output_path
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR, ROOT_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


class AgenteIA(BaseModel):
    id: str = Field(..., min_length=1)
    nombre_oficial: str = Field(..., min_length=2)
    empresa: str = Field(...)
    categoria: str = Field(...)
    estado: str = Field(...)
    es_open_source: bool
    anio_lanzamiento: Optional[int] = Field(None, ge=1950, le=2030)


def extract_and_validate_catalog(run_id=None):
    """Lee el maestro local, valida Pydantic y guarda un Raw inmutable."""
    global_logger.info("Iniciando validacion Pydantic del catalogo maestro...")
    source_path = ROOT_DIR / "data" / "manual" / "maestro_agentes.json"

    if not source_path.exists():
        global_logger.warning("Archivo maestro_agentes.json no encontrado.")
        return log_source_execution("catalogo", "failed", 0, None, str(source_path), notes="Archivo no encontrado", run_id=run_id)

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        valid_records = []
        for index, item in enumerate(data):
            try:
                agente_valido = AgenteIA(**item)
                valid_records.append(agente_valido.model_dump())
            except ValidationError as exc:
                log_error("file_catalog", "PydanticValidationError", f"Fila {index} invalida: {exc}", "Registro omitido", run_id=run_id)

        global_logger.info(f"Catalogo validado: {len(valid_records)}/{len(data)} registros correctos.")

        out_path = raw_output_path("catalogo", run_id=run_id, raw_dir=RAW_DIR)

        with open(out_path, "w", encoding="utf-8") as f:
            payload = {
                "metadata": {
                    "source": "catalogo",
                    "date_range_start": SOURCE_START_DATE,
                    "date_range_end": SOURCE_END_DATE,
                    "records_extracted": len(valid_records),
                    "extracted_at": datetime.datetime.now().isoformat(),
                },
                "items": valid_records,
            }
            json.dump(payload, f, ensure_ascii=False, indent=2)

        global_logger.info(f"Catalogo guardado en Raw: {out_path.name}")
        invalid_count = len(data) - len(valid_records)
        return log_source_execution(
            "catalogo",
            "partial_success" if invalid_count and valid_records else ("failed" if invalid_count else ("success" if valid_records else "empty")),
            len(valid_records),
            None,
            str(source_path),
            out_path,
            notes=f"{invalid_count} registros invalidos" if invalid_count else None,
            run_id=run_id,
        )

    except Exception as exc:
        log_error("file_catalog", type(exc).__name__, str(exc), "Abortado extractor de archivo", run_id=run_id)
        global_logger.error(f"Fallo critico en validacion de catalogo: {exc}")
        return log_source_execution("catalogo", "failed", 0, None, str(source_path), notes=str(exc), run_id=run_id)


if __name__ == "__main__":
    extract_and_validate_catalog()
