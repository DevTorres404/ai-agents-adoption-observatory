import datetime
import json
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


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
DEV_TERMS = ["code", "coding", "programming", "developer", "software", "debug", "ide", "github"]

SEARCH_QUERIES = [
    "AI coding agent",
    "GitHub Copilot programming",
    "Cursor AI coding",
    "Claude Code developer",
    "Devin AI software engineer",
    "Codeium Tabnine coding assistant",
]

SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


def is_relevant(title):
    text = title.lower()
    has_agent = any(term in text for term in AGENT_TERMS)
    has_ai_context = any(term in text for term in AI_TERMS)
    has_dev_context = any(term in text for term in DEV_TERMS)
    return has_agent or (has_ai_context and has_dev_context)


def collect_posts_for_query(page, query, max_per_query=15):
    url = f"https://www.reddit.com/search/?q={quote_plus(query)}&sort=relevance&t=all"
    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    http_status = response.status if response else None

    try:
        page.wait_for_selector("a[data-testid='post-title']", timeout=15000)
    except Exception:
        return [], http_status, url

    for _ in range(3):
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(1200)

    records = []
    posts = page.locator("a[data-testid='post-title']").all()
    for post in posts:
        if len(records) >= max_per_query:
            break
        title = post.inner_text().strip()
        if not title or not is_relevant(title):
            continue
        href = post.get_attribute("href") or ""
        link = href if href.startswith("http") else "https://reddit.com" + href
        records.append({
            "id": link,
            "title": title,
            "url": link,
            "platform": "reddit",
            "source": "reddit",
            "http_status": http_status,
            "search_query": query,
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "created_at": datetime.datetime.now().isoformat(),
        })

    return records, http_status, url


def extract_reddit(max_records=60):
    """Scrapea Reddit con Playwright y filtra posts relevantes sobre IA aplicada al desarrollo."""
    global_logger.info("Iniciando scraping dinamico relevante en Reddit (Playwright)...")
    records_by_id = {}
    status_codes = []
    visited_urls = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            for query in SEARCH_QUERIES:
                if len(records_by_id) >= max_records:
                    break
                query_records, http_status, url = collect_posts_for_query(page, query)
                status_codes.append(http_status)
                visited_urls.append(url)
                for record in query_records:
                    records_by_id[record["id"]] = record

            browser.close()

    except Exception as exc:
        log_error("reddit_scraper", type(exc).__name__, str(exc), "Scraping abortado")
        log_source_execution("reddit", "failed", len(records_by_id), None, ";".join(visited_urls), notes=str(exc))
        global_logger.error(f"Fallo en scraper dinamico Reddit: {exc}")
        return

    records = list(records_by_id.values())[:max_records]
    if not records:
        global_logger.warning("Reddit no arrojo resultados relevantes.")
        log_source_execution("reddit", "empty", 0, status_codes[-1] if status_codes else None, ";".join(visited_urls))
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "scraping" / "reddit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"reddit_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "reddit",
            "urls": visited_urls,
            "http_statuses": status_codes,
            "records_extracted": len(records),
            "search_queries": SEARCH_QUERIES,
            "relevance_rule": "agent term OR (AI term AND software-development term)",
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "date_note": "Reddit UI no expone fecha historica estable en este scraper; Staging aplica filtro 2023-2026.",
            "max_records": max_records,
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    log_source_execution("reddit", "success", len(records), status_codes[-1] if status_codes else None, ";".join(visited_urls), out_path)
    global_logger.info(f"Reddit scraping completado. {len(records)} registros relevantes guardados.")


if __name__ == "__main__":
    extract_reddit()
