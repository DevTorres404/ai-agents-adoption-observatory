import datetime
import json
import time

from pytrends.request import TrendReq

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


def extract_trends():
    """Extrae interes en el tiempo desde Google Trends con manejo explicito de rate limit."""
    global_logger.info("Iniciando extraccion de Google Trends (pytrends)...")
    # Google Trends permite máximo 5 keywords por consulta.
    all_agents = [
        "Cursor AI", "Claude Code", "OpenAI Codex", "GitHub Copilot", "Cline agent",
        "Roo Code", "Windsurf AI", "Aider AI", "Augment Code", "JetBrains Junie",
        "Gemini CLI", "AWS Kiro", "Kilo Code", "Zencoder"
    ]
    
    url = "https://trends.google.com/trends/explore"
    records = []
    extracted_at = datetime.datetime.now().isoformat()
    
    try:
        pytrend = TrendReq(hl="en-US", tz=360)
        
        # Chunking list into 5 items max
        chunks = [all_agents[i:i + 5] for i in range(0, len(all_agents), 5)]
        for kw_list in chunks:
            try:
                pytrend.build_payload(kw_list, cat=0, timeframe=f"{SOURCE_START_DATE} {SOURCE_END_DATE}", geo="")
                df = pytrend.interest_over_time()

                if df.empty:
                    continue

                if "isPartial" in df.columns:
                    df = df.drop(columns=["isPartial"])

                df = df.reset_index()

                for _, row in df.iterrows():
                    fecha = row["date"].isoformat()
                    for keyword in kw_list:
                        if keyword in row:
                            records.append({
                                "agente": keyword,
                                "fecha": fecha,
                                "valor": int(row[keyword]),
                                "fuente": "google_trends",
                                "source": "google_trends",
                                "extracted_at": extracted_at,
                            })
            except Exception as e:
                global_logger.warning(f"Error fetching chunk {kw_list} from trends: {e}")
            
            global_logger.info(f"Pausa de 60s antes del siguiente chunk de Google Trends...")
            time.sleep(60)

        if not records:
            log_source_execution("google_trends", "empty", 0, 200, url, notes="Sin datos")
            return

        date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        out_dir = RAW_DIR / "google_trends"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"google_trends_{date_stamp}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            payload = {
                "metadata": {
                    "source": "google_trends",
                    "keywords": all_agents,
                    "date_range_start": SOURCE_START_DATE,
                    "date_range_end": SOURCE_END_DATE,
                    "records_extracted": len(records),
                    "extracted_at": extracted_at,
                },
                "items": records,
            }
            json.dump(payload, f, ensure_ascii=False, indent=2)

        global_logger.info(f"Google Trends extraido: {len(records)} data points guardados.")
        log_source_execution("google_trends", "success", len(records), 200, url, out_path)

    except Exception as exc:
        http_status = 429 if "429" in str(exc) or "TooManyRequests" in type(exc).__name__ else None
        action = "Rate limit documentado; se conservan datos Raw previos si existen." if http_status == 429 else "Fallo en Pytrends"
        log_error("google_trends", type(exc).__name__, str(exc), action)
        log_source_execution("google_trends", "failed", 0, http_status, url, notes=str(exc))
        global_logger.error(f"Fallo en Pytrends: {exc}")


if __name__ == "__main__":
    extract_trends()
