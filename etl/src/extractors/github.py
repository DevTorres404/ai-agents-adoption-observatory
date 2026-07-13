import datetime
import json

from src.config.settings import GITHUB_TOKEN
from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


def extract_github_repos(queries=None, pages=5, per_page=100):
    """
    Consume la API REST de GitHub Search Repositories y guarda payload Raw con metadata.
    """
    if queries is None:
        queries = ["Cursor", "Claude Code", "Codex", "GitHub Copilot", "Cline", "RooCode", "Windsurf", "Aider", "Augment", "JetBrains Junie", "Gemini CLI", "AWS Kiro", "Kilo Code", "Zencoder"]

    client = HttpClient(source_name="github", default_delay=2, timeout=15)
    headers = {"Accept": "application/vnd.github.v3+json"}

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        global_logger.info("Usando autenticacion GITHUB_TOKEN.")
    else:
        global_logger.warning("Ejecutando GitHub sin token. Sujeto a rate limit anonimo.")

    all_items = []
    endpoint = "https://api.github.com/search/repositories"
    last_status = None

    for query in queries:
        global_logger.info(f"Buscando repositorios para: '{query}'")
        for page in range(1, pages + 1):
            params = {
                "q": f"{query} created:{SOURCE_START_DATE}..{SOURCE_END_DATE}",
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }

            try:
                response = client.get(endpoint, params=params, headers=headers)
                last_status = response.status_code
                data = response.json()
                items = data.get("items", [])

                if not items:
                    global_logger.info(f"Paginacion agotada en pagina {page} para '{query}'")
                    break

                all_items.extend(items)
                global_logger.info(f"Pagina {page} obtenida ({len(items)} repositorios)")

                remaining = int(response.headers.get("X-RateLimit-Remaining", 100))
                if remaining < 5:
                    global_logger.warning(f"Rate limit casi agotado ({remaining} restantes).")

            except Exception as exc:
                log_error("github", type(exc).__name__, str(exc), "Paginacion abortada para esta query")
                log_source_execution("github", "failed", len(all_items), client.last_status_code, endpoint, notes=str(exc))
                break

    target_dir = RAW_DIR / "github"
    target_dir.mkdir(parents=True, exist_ok=True)

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"github_{date_stamp}.json"
    filepath = target_dir / filename

    payload = {
        "metadata": {
            "source": "github",
            "endpoint": "search/repositories",
            "url": endpoint,
            "http_status": last_status,
            "queries": queries,
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "pages_requested_per_query": pages,
            "per_page_limit": per_page,
            "total_count_extracted": len(all_items),
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": all_items,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    status = "success" if all_items else "empty"
    log_source_execution("github", status, len(all_items), last_status, endpoint, filepath)
    global_logger.info(f"Extraccion GitHub completada: {len(all_items)} registros guardados en {filename}")


if __name__ == "__main__":
    global_logger.info(">>> PRUEBA INDEPENDIENTE DE EXTRACTOR GITHUB <<<")
    extract_github_repos(queries=["AI agent"], pages=1, per_page=10)
