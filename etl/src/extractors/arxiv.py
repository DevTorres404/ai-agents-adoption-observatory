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

def extract_arxiv(max_per_agent=20, run_id=None, sleeper=time.sleep):
    global_logger.info("Iniciando extracción en arXiv API...")
    client = HttpClient(source_name="arxiv")
    records = []
    query_results = []
    last_url = None
    
    for agent_query in AGENT_QUERIES:
        query = urllib.parse.quote(f'all:"{agent_query}"')
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_per_agent}&sortBy=submittedDate&sortOrder=descending"
        last_url = url
        
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
            query_results.append(
                log_source_execution(
                    "arxiv", "success" if entries else "empty", len(entries),
                    client.last_status_code, url, run_id=run_id, query=agent_query,
                )
            )
            sleeper(3)
            
        except Exception as exc:
            global_logger.error(f"Error consultando arXiv para {agent_query}: {exc}")
            log_error("arxiv", type(exc).__name__, str(exc), f"Agente: {agent_query}", run_id=run_id)
            query_results.append(
                log_source_execution(
                    "arxiv", "failed", 0, client.last_status_code, url,
                    notes=str(exc), run_id=run_id, query=agent_query,
                )
            )

    records = list({record["id"]: record for record in records}.values())
    status = aggregate_status(query_results)
    if not records:
        global_logger.warning("arXiv no arrojó resultados.")
        return log_source_execution(
            "arxiv", status, 0, client.last_status_code, last_url,
            notes="Sin datos; consulte resultados por query", run_id=run_id,
        )

    out_path = raw_output_path("arxiv", run_id=run_id, raw_dir=RAW_DIR)

    payload = {
        "metadata": {
            "source": "api_arxiv",
            "records_extracted": len(records),
            "status": status.value,
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"arXiv extracción completada. {len(records)} registros guardados.")
    return log_source_execution(
        "arxiv", status, len(records), client.last_status_code, last_url,
        out_path, run_id=run_id,
    )

if __name__ == "__main__":
    extract_arxiv()
