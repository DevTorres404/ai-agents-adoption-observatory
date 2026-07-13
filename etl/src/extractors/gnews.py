import datetime
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET

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

def extract_gnews():
    global_logger.info("Iniciando extracción en Google News RSS...")
    client = HttpClient(source_name="gnews")
    records = []
    
    for agent_query in AGENT_QUERIES:
        query = urllib.parse.quote(f'"{agent_query}"')
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        
        try:
            response_text = client.get(url, is_json=False)
            root = ET.fromstring(response_text)
            
            channel = root.find('channel')
            if channel is not None:
                items = channel.findall('item')
                for item in items:
                    title = item.find('title').text if item.find('title') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                    
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
                    })
                    
                global_logger.info(f"Google News: {len(items)} noticias para '{agent_query}'.")
            
            time.sleep(2) # Respetar limites
            
        except Exception as exc:
            global_logger.error(f"Error consultando GNews para {agent_query}: {exc}")
            log_error("gnews", type(exc).__name__, str(exc), f"Agente: {agent_query}")

    if not records:
        global_logger.warning("Google News no arrojó resultados.")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "gnews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gnews_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "rss_gnews",
            "records_extracted": len(records),
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"Google News extracción completada. {len(records)} registros guardados.")
    log_source_execution("rss_gnews", "success", len(records), client.last_status_code, url, out_path)

if __name__ == "__main__":
    extract_gnews()
