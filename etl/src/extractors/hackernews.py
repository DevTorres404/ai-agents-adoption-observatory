import datetime
import json
import time

from src.utils.error_log import log_error
from src.utils.extraction_window import resolve_window
from src.utils.extraction_evidence import aggregate_status, log_source_execution, raw_output_path
from src.utils.http_client import HttpClient
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR
from src.utils.time_utils import ECUADOR_TZ, now_local, to_ec_naive


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"

# Algolia HN Search: historico completo desde 2006, sin API key (~10k req/h por IP).
# search_by_date ordena por created_at_i desc, lo que hace estable el recorte temporal.
ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HITS_PER_PAGE = 1000

# IMPORTANTE: Algolia fija paginationLimitedTo=1000 en este indice, asi que la pagina
# 1 y siguientes SIEMPRE vienen vacias, sin importar nbHits ni hitsPerPage (verificado:
# Cursor 2025 -> nbHits=1636, page=1 -> 0 hits; con hitsPerPage=100 la pagina 10 tambien
# devuelve 0). Por eso NO se pagina: cuando una ventana devuelve HITS_PER_PAGE hits se
# biseca el rango temporal y se consultan las dos mitades, hasta que cada subventana
# quepa completa en una sola respuesta. La suma de las mitades reproduce el total real
# (Cursor 2025: 809 + 828 = 1637).
MIN_WINDOW_SECONDS = 3600  # no dividir por debajo de 1h (techo de recursion)
MAX_REQUESTS_PER_TERM = 600  # presupuesto defensivo de peticiones por termino

HTTP_DELAY_SECONDS = 0.5  # Algolia tolera 10k req/h por IP; el limite real es el presupuesto

AGENT_QUERIES = ["Codex", "GitHub Copilot Coding Agent", "Cursor Agent", "Windsurf Cascade", "Devin", "OpenCode", "Claude Code", "Cline", "Google Antigravity", "Google Jules"]


def _epoch(dt):
    return int(dt.timestamp())


def _ec_midnight(year, month=1, day=1):
    return datetime.datetime(year, month, day, tzinfo=ECUADOR_TZ)


def _window_bounds(end_ts, start_date=None):
    """Inclusive annual slices without hard-coded study years."""
    start_date = start_date or datetime.date.fromisoformat(SOURCE_START_DATE)
    start_ts = _epoch(_ec_midnight(start_date.year, start_date.month, start_date.day))
    end_year = datetime.datetime.fromtimestamp(end_ts, ECUADOR_TZ).year
    return [(year, max(start_ts, _epoch(_ec_midnight(year))),
             min(end_ts, _epoch(_ec_midnight(year + 1)) - 1))
            for year in range(start_date.year, end_year + 1)
            if max(start_ts, _epoch(_ec_midnight(year))) <= end_ts]


def _fetch_page(client, term, window_start, window_end, sleeper, attempts=3):
    """GET a Algolia con reintentos simples ante timeouts/429/errores transitorios."""
    params = {
        "query": term,
        "tags": "story",
        "numericFilters": f"created_at_i>={window_start},created_at_i<={window_end}",
        "hitsPerPage": HITS_PER_PAGE,
        "page": 0,
    }
    last_exc = None
    for attempt in range(attempts):
        try:
            return client.get(ALGOLIA_SEARCH_URL, params=params, is_json=True)
        except Exception as exc:  # RateLimitError/Timeout/RequestException
            last_exc = exc
            if attempt < attempts - 1:
                sleeper(2.0 * (attempt + 1))
    raise last_exc


def _fetch_window(client, term, window_start, window_end, sleeper, budget, unsplittable):
    """Devuelve TODOS los hits de una ventana, bisecando el rango si excede el tope.

    Algolia solo permite recuperar 1000 hits por consulta (paginationLimitedTo), asi
    que una ventana con mas hits se parte por la mitad en tiempo y se consultan ambas
    mitades de forma recursiva. `budget` es un contador mutable compartido por termino
    y `unsplittable` acumula las subventanas que ya no se pueden dividir mas.
    """
    if budget["requests"] <= 0:
        budget["exhausted"] = True
        return []
    budget["requests"] -= 1

    data = _fetch_page(client, term, window_start, window_end, sleeper)
    hits = data.get("hits") or []
    if len(hits) < HITS_PER_PAGE:
        return hits

    if int(data.get("nbHits") or 0) <= HITS_PER_PAGE:
        return hits  # la respuesta contiene todo lo que el indice expone

    if (window_end - window_start) < MIN_WINDOW_SECONDS:
        unsplittable.append((window_start, window_end, int(data.get("nbHits") or 0)))
        return hits

    mid = (window_start + window_end) // 2
    return _fetch_window(
        client, term, window_start, mid, sleeper, budget, unsplittable
    ) + _fetch_window(
        client, term, mid + 1, window_end, sleeper, budget, unsplittable
    )


def _hit_to_record(hit, http_status):
    created_ts = hit.get("created_at_i")
    object_id = str(hit.get("objectID") or "")
    if created_ts is None or not object_id:
        return None
    created_at = to_ec_naive(
        datetime.datetime.fromtimestamp(int(created_ts), ECUADOR_TZ)
    ).isoformat()
    return {
        "id": object_id,
        "title": hit.get("title") or "",
        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
        "points": int(hit.get("points") or 0),
        "num_comments": int(hit.get("num_comments") or 0),
        "created_at": created_at,
        "source": "hackernews",
        "http_status": http_status,
    }


def extract_hackernews(run_id=None, sleeper=time.sleep, start_date=None, end_date=None):
    """Extrae stories historicas de HackerNews via Algolia Search en el rango solicitado.

    Reemplaza el scrapeo de la portada (que solo daba ~30 filas con la fecha de
    extraccion) por busqueda con fecha real de publicacion (created_at_i) y
    biseccion temporal; ver HITS_PER_PAGE para el tope de paginacion de Algolia.
    """
    global_logger.info("Iniciando extraccion historica en HackerNews (Algolia API)...")
    client = HttpClient(source_name="hackernews", timeout=30, default_delay=HTTP_DELAY_SECONDS)
    records = []
    query_results = []
    window = resolve_window(start_date, end_date, default_start=SOURCE_START_DATE, default_end=SOURCE_END_DATE)
    end_exclusive = window.end + datetime.timedelta(days=1)
    end_ts = min(_epoch(now_local()), _epoch(_ec_midnight(end_exclusive.year, end_exclusive.month, end_exclusive.day)) - 1)
    windows = _window_bounds(end_ts, window.start)

    for agent_query in AGENT_QUERIES:
        records_for_query = 0
        seen = set()
        query_failed = None
        unsplittable = []
        budget = {"requests": MAX_REQUESTS_PER_TERM, "exhausted": False}

        for year, window_start, window_end in windows:
            try:
                hits = _fetch_window(
                    client, agent_query, window_start, window_end, sleeper, budget, unsplittable
                )
                for hit in hits:
                    record = _hit_to_record(hit, client.last_status_code)
                    if record and record["id"] not in seen:
                        seen.add(record["id"])
                        records.append(record)
                        records_for_query += 1
            except Exception as exc:
                query_failed = exc
                global_logger.error(f"Error consultando HackerNews para '{agent_query}' ({year}): {exc}")
                log_error("hackernews", type(exc).__name__, str(exc), f"Agente: {agent_query} ({year})", run_id=run_id)
                break
            if budget["exhausted"]:
                global_logger.warning(
                    f"HackerNews: presupuesto de {MAX_REQUESTS_PER_TERM} peticiones agotado en '{agent_query}'."
                )
                break

        for start, end, nb_hits in unsplittable:
            global_logger.warning(
                f"HackerNews: '{agent_query}' con {nb_hits} hits en la subventana "
                f"[{start}, {end}] no divisible mas alla de {MIN_WINDOW_SECONDS}s; recorte en {HITS_PER_PAGE}."
            )

        notes = []
        if query_failed:
            notes.append(str(query_failed))
        if budget["exhausted"]:
            notes.append(f"presupuesto de {MAX_REQUESTS_PER_TERM} peticiones agotado")
        if unsplittable:
            notes.append(f"{len(unsplittable)} subventana(s) con mas de {HITS_PER_PAGE} hits sin divisibilidad")

        incomplete = bool(notes)
        if incomplete:
            query_status = "partial_success" if records_for_query else "failed"
        else:
            query_status = "success" if records_for_query else "empty"
        query_results.append(
            log_source_execution(
                "hackernews",
                query_status,
                records_for_query,
                client.last_status_code,
                ALGOLIA_SEARCH_URL,
                notes="; ".join(notes) if notes else None,
                run_id=run_id,
                query=agent_query,
            )
        )

    records = list({record["id"]: record for record in records}.values())
    status = aggregate_status(query_results)
    if not records:
        global_logger.warning("HackerNews no arrojo registros.")
        return log_source_execution(
            "hackernews", status, 0, client.last_status_code, ALGOLIA_SEARCH_URL,
            notes="Sin datos; consulte resultados por query", run_id=run_id,
        )

    out_path = raw_output_path("hackernews", run_id=run_id, raw_dir=RAW_DIR)

    payload = {
        "metadata": {
            "source": "hackernews",
            "api": "api/v1/search_by_date",
            "url": ALGOLIA_SEARCH_URL,
            "http_status": client.last_status_code,
            "status": status.value,
            "date_range_start": window.start.isoformat(),
            "date_range_end": window.end.isoformat(),
            "effective_end_timestamp": end_ts,
            "records_extracted": len(records),
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
            "extracted_at": to_ec_naive(now_local()).isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"HackerNews extraccion completada. {len(records)} registros guardados en {out_path.name}")
    return log_source_execution(
        "hackernews", status, len(records), client.last_status_code, ALGOLIA_SEARCH_URL,
        out_path,
        notes=f"{sum(item.status.value in {'failed', 'partial_success'} for item in query_results)} consultas con incidentes",
        run_id=run_id,
    )


if __name__ == "__main__":
    extract_hackernews()
