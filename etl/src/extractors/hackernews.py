import datetime
import json

from bs4 import BeautifulSoup

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


def extract_hackernews():
    """Scrapea HTML de HackerNews y guarda evidencia Raw verificable."""
    global_logger.info("Iniciando scraping estatico en HackerNews...")
    client = HttpClient(source_name="hackernews")
    url = "https://news.ycombinator.com/front"

    try:
        html = client.get(url, is_json=False)
    except Exception as exc:
        log_error("hackernews", type(exc).__name__, str(exc), "Scraping abortado")
        log_source_execution("hackernews", "failed", 0, client.last_status_code, url, notes=str(exc))
        return

    if not html:
        global_logger.warning("HackerNews devolvio HTML vacio.")
        log_source_execution("hackernews", "failed", 0, client.last_status_code, url, notes="HTML vacio")
        return

    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("tr", class_="athing")

    records = []
    for item in items:
        try:
            title_tag = item.find("span", class_="titleline").find("a")
            title = title_tag.text.strip() if title_tag else ""
            link = title_tag["href"] if title_tag else ""

            next_row = item.find_next_sibling("tr")
            score_tag = next_row.find("span", class_="score") if next_row else None
            comments_tag = next_row.find_all("a")[-1] if next_row and next_row.find_all("a") else None
            score_str = score_tag.text.replace(" points", "") if score_tag else "0"
            comments_str = comments_tag.text.replace(" comments", "") if comments_tag else "0"

            records.append({
                "id": item.get("id", ""),
                "title": title,
                "url": link,
                "points": int(score_str) if score_str.isdigit() else 0,
                "num_comments": int(comments_str) if comments_str.isdigit() else 0,
                "created_at": datetime.datetime.now().isoformat(),
                "source": "hackernews",
                "http_status": client.last_status_code,
                "date_range_start": SOURCE_START_DATE,
                "date_range_end": SOURCE_END_DATE,
            })
        except Exception as exc:
            global_logger.warning(f"HackerNews: fila omitida por parseo: {exc}")

    if not records:
        global_logger.warning("HackerNews no arrojo registros parseables.")
        log_source_execution("hackernews", "empty", 0, client.last_status_code, url, notes="Sin registros parseables")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "hackernews"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"hackernews_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "hackernews",
            "url": url,
            "http_status": client.last_status_code,
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "records_extracted": len(records),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"HackerNews scraping completado. {len(records)} registros guardados en {out_path.name}")
    log_source_execution("hackernews", "success", len(records), client.last_status_code, url, out_path)


if __name__ == "__main__":
    extract_hackernews()
