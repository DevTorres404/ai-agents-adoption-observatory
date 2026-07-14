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

def extract_arxiv(max_per_agent=20):
    global_logger.info("Iniciando extracción en arXiv API...")
    client = HttpClient(source_name="arxiv")
    records = []
    
    for agent_query in AGENT_QUERIES:
        query = urllib.parse.quote(f'all:"{agent_query}"')
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_per_agent}&sortBy=submittedDate&sortOrder=descending"
        
        try:
            response_text = client.get(url, is_json=False)
            root = ET.fromstring(response_text)
            
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', ns)
            
            for entry in entries:
                published = entry.find('atom:published', ns).text
                created_at = datetime.datetime.fromisoformat(published.replace('Z', '+00:00')).isoformat()
                
                title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
                summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
                link = entry.find('atom:id', ns).text
                categories = [
                    category.get('term')
                    for category in entry.findall('atom:category', ns)
                    if category.get('term')
                ]
                
                records.append({
                    "id": link,
                    "title": title,
                    "description": summary,
                    "url": link,
                    "created_at": created_at,
                    "platform": "arxiv",
                    "source": "api_arxiv",
                    "agent_search": agent_query,
                    "categories": categories,
                })
                
            global_logger.info(f"arXiv: {len(entries)} papers para '{agent_query}'.")
            time.sleep(3) # Respetar rate limits de arxiv
            
        except Exception as exc:
            global_logger.error(f"Error consultando arXiv para {agent_query}: {exc}")
            log_error("arxiv", type(exc).__name__, str(exc), f"Agente: {agent_query}")

    if not records:
        global_logger.warning("arXiv no arrojó resultados.")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "arxiv"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"arxiv_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "api_arxiv",
            "records_extracted": len(records),
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"arXiv extracción completada. {len(records)} registros guardados.")
    log_source_execution("api_arxiv", "success", len(records), client.last_status_code, url, out_path)

if __name__ == "__main__":
    extract_arxiv()
