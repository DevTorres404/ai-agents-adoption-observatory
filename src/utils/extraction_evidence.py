import csv
import datetime
from src.utils.paths import ROOT_DIR
from src.utils.logger import global_logger


EVIDENCE_FILE = ROOT_DIR / "docs" / "evidencias" / "source_execution_evidence.csv"


def log_source_execution(source, status, records_extracted=0, http_status=None, url=None, raw_path=None, notes=None):
    """
    Registra evidencia verificable por fuente. Una fuente fallida se registra como fallida,
    no como extraccion exitosa.
    """
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = EVIDENCE_FILE.exists()
    row = {
        "execution_timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "status": status,
        "records_extracted": records_extracted,
        "http_status": http_status,
        "url": url,
        "raw_path": str(raw_path).replace("\\", "/") if raw_path else "",
        "notes": notes or "",
    }

    with open(EVIDENCE_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    global_logger.info(
        f"Evidencia fuente {source}: status={status}, records={records_extracted}, http={http_status}"
    )
