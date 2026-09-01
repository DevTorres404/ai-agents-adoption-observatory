import datetime
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET

from src.utils.error_log import log_error
from src.utils.extraction_evidence import aggregate_status, log_source_execution, raw_output_path
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

def extract_gnews(run_id=None, sleeper=time.sleep):
    global_logger.info("Iniciando extracción en Google News RSS...")
    client = HttpClient(source_name="gnews")
    records = []
    query_results = []
    last_url = None
    
    for agent_query in AGENT_QUERIES:
        query = urllib.parse.quote(f'"{agent_query}"')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        last_url = url
        
        try:
            response_text = client.get(url, is_json=False)
            root = ET.fromstring(response_text)
            items = []
            channel = root.find('channel')
            if channel is not None:
                items = channel.findall('item')
                for item in items:
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    publisher = item.find('source').text if item.find('source') is not None else ""
                    
                    try:
                        # pubDate form: "Thu, 26 Oct 2023 07:00:00 GMT"
                        parsed_date = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
                        created_at = parsed_date.isoformat()
                    except:
                        created_at = datetime.datetime.now().isoformat()
                    
                    records.append({
                        "id": link,
                        "title": title,
                        "description": "",
                        "url": link,
                        "created_at": created_at,
                        "platform": "google_news",
                        "source": "rss_gnews",
                        "agent_search": agent_query,
                        "publisher": publisher,
                    })
                    
                global_logger.info(f"Google News: {len(items)} noticias para '{agent_query}'.")

            query_results.append(
                log_source_execution(
                    "gnews",
                    "success" if items else "empty",
                    len(items),
                    client.last_status_code,
                    url,
                    run_id=run_id,
                    query=agent_query,
                )
            )
            
            sleeper(2)
            
        except Exception as exc:
            global_logger.error(f"Error consultando GNews para {agent_query}: {exc}")
            log_error(
                "gnews",
                type(exc).__name__,
                str(exc),
                f"Agente: {agent_query}",
                run_id=run_id,
            )
            query_results.append(
                log_source_execution(
                    "gnews",
                    "failed",
                    0,
                    client.last_status_code,
                    url,
                    notes=str(exc),
                    run_id=run_id,
                    query=agent_query,
                )
            )

    status = aggregate_status(query_results)
    if not records:
        global_logger.warning("Google News no arrojó resultados.")
        return log_source_execution(
            "gnews",
            status,
            0,
            client.last_status_code,
            last_url,
            notes="Sin registros; consulte los resultados por query",
            run_id=run_id,
        )

    out_path = raw_output_path("gnews", run_id=run_id, raw_dir=RAW_DIR)

    payload = {
        "metadata": {
            "source": "rss_gnews",
            "records_extracted": len(records),
            "status": status.value,
            "query_results": [
                {
                    "query": result.query,
                    "status": result.status.value,
                    "records_extracted": result.records_extracted,
                    "http_status": result.http_status,
                    "notes": result.notes,
                }
                for result in query_results
            ],
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"Google News extracción completada. {len(records)} registros guardados.")
    return log_source_execution(
        "gnews",
        status,
        len(records),
        client.last_status_code,
        last_url,
        out_path,
        notes=f"{sum(item.status.value in {'failed', 'partial_success'} for item in query_results)} consultas con incidentes",
        run_id=run_id,
    )

if __name__ == "__main__":
    extract_gnews()
