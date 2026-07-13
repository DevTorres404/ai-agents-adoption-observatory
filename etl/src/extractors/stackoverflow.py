import datetime
import json
import time

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = datetime.date(2023, 1, 1)
SOURCE_END_DATE = datetime.date(2026, 12, 31)

AGENT_QUERIES = [
    "Cursor AI", "Claude Code", "OpenAI Codex", "GitHub Copilot", "Cline agent",
    "Roo Code", "Windsurf AI", "Aider AI", "Augment Code", "JetBrains Junie",
    "Gemini CLI", "AWS Kiro", "Kilo Code", "Zencoder"
]

def extract_stackoverflow(max_per_agent=50):
    global_logger.info("Iniciando extracción en StackOverflow API...")
    client = HttpClient(source_name="stackoverflow")
    records = []
    
    start_ts = int(datetime.datetime(2023, 1, 1).timestamp())
    end_ts = int(datetime.datetime.now().timestamp())
    
    for agent_query in AGENT_QUERIES:
        url = "https://api.stackexchange.com/2.3/search/advanced"
        records_for_agent = 0
        pages_needed = (max_per_agent // 100) + (1 if max_per_agent % 100 > 0 else 0)
        
        for page in range(1, pages_needed + 1):
            if records_for_agent >= max_per_agent:
                break
                
            params = {
                "order": "desc",
                "sort": "creation",
                "q": agent_query,
                "site": "stackoverflow",
                "fromdate": start_ts,
                "todate": end_ts,
                "pagesize": 100,
                "page": page,
                "filter": "!9_bDDxJY5" # Includes body
            }
            
            try:
                response = client.get(url, params=params)
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break
                    
                for item in items:
                    if records_for_agent >= max_per_agent:
                        break
                    creation_date = datetime.datetime.fromtimestamp(item.get("creation_date")).isoformat()
                    records.append({
                        "id": str(item.get("question_id")),
                        "title": item.get("title", ""),
                        "description": item.get("body_markdown", "") or item.get("body", ""),
                        "url": item.get("link", ""),
                        "created_at": creation_date,
                        "platform": "stackoverflow",
                        "source": "api_stackoverflow",
                        "agent_search": agent_query,
                        "score": item.get("score", 0),
                        "view_count": item.get("view_count", 0),
                        "answer_count": item.get("answer_count", 0),
                        "tags": item.get("tags", [])
                    })
                    records_for_agent += 1
                
                global_logger.info(f"StackOverflow: obteniendo página {page} para '{agent_query}'.")
                time.sleep(1.5) # Respetar rate limits
                
            except Exception as exc:
                global_logger.error(f"Error consultando StackOverflow para {agent_query}: {exc}")
                log_error("stackoverflow", type(exc).__name__, str(exc), f"Agente: {agent_query}")
                break

    if not records:
        global_logger.warning("StackOverflow no arrojó resultados.")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "stackoverflow"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"stackoverflow_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "api_stackoverflow",
            "records_extracted": len(records),
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"StackOverflow extracción completada. {len(records)} registros guardados.")
    log_source_execution("api_stackoverflow", "success", len(records), client.last_status_code, url, out_path)

if __name__ == "__main__":
    extract_stackoverflow()
