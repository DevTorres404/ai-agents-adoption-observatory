import datetime
import json
import math

from src.config.settings import GITHUB_TOKEN
from src.utils.error_log import log_error
from src.utils.extraction_evidence import (
    ExtractionStatus,
    aggregate_status,
    log_source_execution,
    raw_output_path,
)
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"
MAX_RESULTS_PER_PARTITION = 1000
MAX_PAGES_PER_PARTITION = 10
MAX_PARTITION_DEPTH = 16


def _split_date_range(start_date, end_date):
    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)
    if start >= end:
        return None
    midpoint = start + (end - start) // 2
    return (
        (start.isoformat(), midpoint.isoformat()),
        ((midpoint + datetime.timedelta(days=1)).isoformat(), end.isoformat()),
    )


def _item_key(item):
    return item.get("id") or item.get("full_name") or item.get("html_url") or repr(item)


def _search_partition(
    client,
    endpoint,
    headers,
    query,
    start_date,
    end_date,
    pages,
    per_page,
    run_id,
    depth=0,
):
    unit = f"{query}|{start_date}..{end_date}"

    def request_page(page):
        return client.get(
            endpoint,
            params={
                "q": f"{query} created:{start_date}..{end_date}",
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            },
            headers=headers,
        )

    try:
        first_response = request_page(1)
        first_data = first_response.json()
        total_count = int(first_data.get("total_count") or 0)
        first_items = first_data.get("items", [])
    except Exception as exc:
        log_error(
            "github",
            type(exc).__name__,
            str(exc),
            "Particion abortada",
            run_id=run_id,
        )
        result = log_source_execution(
            "github",
            ExtractionStatus.FAILED,
            0,
            client.last_status_code,
            endpoint,
            notes=str(exc),
            run_id=run_id,
            query=unit,
        )
        return [], [result]

    split = _split_date_range(start_date, end_date)
    if total_count > MAX_RESULTS_PER_PARTITION and split and depth < MAX_PARTITION_DEPTH:
        records = []
        outcomes = []
        for child_start, child_end in split:
            child_records, child_outcomes = _search_partition(
                client,
                endpoint,
                headers,
                query,
                child_start,
                child_end,
                pages,
                per_page,
                run_id,
                depth + 1,
            )
            records.extend(child_records)
            outcomes.extend(child_outcomes)
        return records, outcomes

    records = list(first_items)
    incomplete = total_count > MAX_RESULTS_PER_PARTITION
    available_pages = max(1, math.ceil(min(total_count, MAX_RESULTS_PER_PARTITION) / per_page))
    pages_to_fetch = min(pages, MAX_PAGES_PER_PARTITION, available_pages)
    failure = None

    for page in range(2, pages_to_fetch + 1):
        try:
            response = request_page(page)
            items = response.json().get("items", [])
            if not items:
                break
            records.extend(items)
        except Exception as exc:
            failure = exc
            log_error(
                "github",
                type(exc).__name__,
                str(exc),
                "Paginacion abortada para esta particion",
                run_id=run_id,
            )
            break

    records = list({_item_key(item): item for item in records}.values())
    if failure or incomplete:
        status = ExtractionStatus.PARTIAL_SUCCESS if records else ExtractionStatus.FAILED
    else:
        status = ExtractionStatus.SUCCESS if records else ExtractionStatus.EMPTY
    notes = []
    if incomplete:
        notes.append(
            f"Particion limitada a {MAX_RESULTS_PER_PARTITION} resultados tras alcanzar profundidad {depth}"
        )
    if failure:
        notes.append(str(failure))
    outcome = log_source_execution(
        "github",
        status,
        len(records),
        client.last_status_code,
        endpoint,
        notes="; ".join(notes) or None,
        run_id=run_id,
        query=unit,
    )
    return records, [outcome]


def extract_github_repos(queries=None, pages=10, per_page=100, run_id=None):
    """Extract repositories without crossing GitHub Search's 1,000-result window."""
    if queries is None:
        queries = [
            "Cursor", "Claude Code", "Codex", "GitHub Copilot", "Cline",
            "RooCode", "Windsurf", "Aider", "Augment", "JetBrains Junie",
            "Gemini CLI", "AWS Kiro", "Kilo Code", "Zencoder",
        ]
    pages = max(1, min(int(pages), MAX_PAGES_PER_PARTITION))
    per_page = max(1, min(int(per_page), 100))

    client = HttpClient(source_name="github", default_delay=2, timeout=15)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        global_logger.info("Usando autenticacion GITHUB_TOKEN.")
    else:
        global_logger.warning("Ejecutando GitHub sin token. Sujeto a rate limit anonimo.")

    endpoint = "https://api.github.com/search/repositories"
    all_items = []
    query_results = []
    for query in queries:
        global_logger.info(f"Buscando repositorios para: '{query}'")
        items, outcomes = _search_partition(
            client,
            endpoint,
            headers,
            query,
            SOURCE_START_DATE,
            SOURCE_END_DATE,
            pages,
            per_page,
            run_id,
        )
        all_items.extend(items)
        query_results.extend(outcomes)

    all_items = list({_item_key(item): item for item in all_items}.values())
    status = aggregate_status(query_results)
    filepath = raw_output_path("github", run_id=run_id, raw_dir=RAW_DIR)
    payload = {
        "metadata": {
            "source": "github",
            "endpoint": "search/repositories",
            "url": endpoint,
            "http_status": client.last_status_code,
            "queries": queries,
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "max_pages_per_partition": pages,
            "per_page_limit": per_page,
            "total_count_extracted": len(all_items),
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
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": all_items,
    }
    with filepath.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)

    result = log_source_execution(
        "github",
        status,
        len(all_items),
        client.last_status_code,
        endpoint,
        filepath,
        notes=f"{sum(item.status in {ExtractionStatus.FAILED, ExtractionStatus.PARTIAL_SUCCESS} for item in query_results)} particiones con incidentes",
        run_id=run_id,
    )
    global_logger.info(
        f"Extraccion GitHub finalizada con status={status.value}: "
        f"{len(all_items)} registros en {filepath.name}"
    )
    return result


if __name__ == "__main__":
    extract_github_repos(queries=["AI agent"], pages=1, per_page=10)
