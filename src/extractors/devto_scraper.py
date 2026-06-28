import datetime
import json

from bs4 import BeautifulSoup

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = datetime.date(2023, 1, 1)
SOURCE_END_DATE = datetime.date(2026, 12, 31)


AGENT_TERMS = [
    "ai agent",
    "coding agent",
    "github copilot",
    "copilot",
    "cursor",
    "claude code",
    "devin",
    "codeium",
    "tabnine",
    "replit ai",
    "autogpt",
    "auto-gpt",
]

AI_TERMS = ["ai", "artificial intelligence", "llm", "generative ai", "agentic"]
DEV_TERMS = [
    "code",
    "coding",
    "programming",
    "developer",
    "software",
    "debug",
    "refactor",
    "ide",
    "github",
    "typescript",
    "python",
]


def is_relevant(item):
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("description", "")),
        " ".join(item.get("tag_list", []) or []),
    ]).lower()
    has_agent = any(term in text for term in AGENT_TERMS)
    has_ai_context = any(term in text for term in AI_TERMS)
    has_dev_context = any(term in text for term in DEV_TERMS)
    return has_agent or (has_ai_context and has_dev_context)


def is_in_date_range(value):
    if not value:
        return True
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        return SOURCE_START_DATE <= parsed <= SOURCE_END_DATE
    except ValueError:
        return True


def article_to_record(item, http_status):
    return {
        "id": str(item.get("id") or item.get("url")),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "created_at": item.get("published_at") or item.get("created_at"),
        "platform": "devto",
        "source": "devto",
        "http_status": http_status,
        "tags": item.get("tag_list", []),
        "description": item.get("description", ""),
        "reactions_count": item.get("positive_reactions_count", 0),
        "comments_count": item.get("comments_count", 0),
    }


def extract_from_html(client, url):
    records = []
    html = client.get(url, is_json=False)
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("div", class_="crayons-story")

    for article in articles[:30]:
        try:
            title_tag = article.find("h2", class_="crayons-story__title").find("a")
            title = title_tag.text.strip() if title_tag else ""
            href = title_tag["href"] if title_tag else ""
            link = href if href.startswith("http") else f"https://dev.to{href}"
            date_tag = article.find("time")
            date_text = date_tag.get("datetime") if date_tag else datetime.datetime.now().date().isoformat()
            candidate = {
                "id": link,
                "title": title,
                "url": link,
                "created_at": date_text,
                "platform": "devto",
                "source": "devto",
                "http_status": client.last_status_code,
                "tags": [],
                "description": "",
            }
            if is_relevant(candidate) and is_in_date_range(candidate["created_at"]):
                records.append(candidate)
        except Exception as exc:
            global_logger.warning(f"Dev.to: articulo HTML omitido por parseo: {exc}")

    return records


def extract_from_public_api(client, max_records=80):
    api_url = "https://dev.to/api/articles"
    tags = ["ai", "programming", "webdev", "python", "javascript", "opensource"]
    records_by_id = {}
    pages_per_tag = 3
    per_page = 30

    for tag in tags:
        for page in range(1, pages_per_tag + 1):
            if len(records_by_id) >= max_records:
                break
            response = client.get(api_url, params={"tag": tag, "per_page": per_page, "page": page})
            for item in response.json():
                if not is_relevant(item) or not is_in_date_range(item.get("published_at") or item.get("created_at")):
                    continue
                record = article_to_record(item, response.status_code)
                records_by_id[record["id"]] = record
        if len(records_by_id) >= max_records:
            break

    return list(records_by_id.values())[:max_records]


def extract_devto(max_records=80):
    """Extrae articulos Dev.to relevantes para agentes de IA en desarrollo."""
    global_logger.info("Iniciando extraccion relevante en Dev.to...")
    client = HttpClient(source_name="devto")
    url = "https://dev.to/search?q=AI%20coding%20agent"
    records = []
    extraction_method = "beautifulsoup_html+public_api"

    try:
        records.extend(extract_from_html(client, url))
        api_records = extract_from_public_api(client, max_records=max_records)
        by_id = {record["id"]: record for record in records}
        by_id.update({record["id"]: record for record in api_records})
        records = [record for record in by_id.values() if is_in_date_range(record.get("created_at"))][:max_records]
    except Exception as exc:
        log_error("devto_scraper", type(exc).__name__, str(exc), "Extraccion Dev.to abortada")
        log_source_execution("devto", "failed", len(records), client.last_status_code, url, notes=str(exc))
        return

    if not records:
        global_logger.warning("Dev.to no arrojo articulos relevantes.")
        log_source_execution("devto", "empty", 0, client.last_status_code, url, notes="Sin articulos relevantes")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "scraping" / "devto"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"devto_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "devto",
            "url": url,
            "http_status": client.last_status_code,
            "records_extracted": len(records),
            "extraction_method": extraction_method,
            "relevance_rule": "agent term OR (AI term AND software-development term)",
            "date_range_start": SOURCE_START_DATE.isoformat(),
            "date_range_end": SOURCE_END_DATE.isoformat(),
            "max_records": max_records,
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"Dev.to extraccion completada. {len(records)} registros relevantes guardados en {out_path.name}")
    log_source_execution("devto", "success", len(records), client.last_status_code, url, out_path)


if __name__ == "__main__":
    extract_devto()
