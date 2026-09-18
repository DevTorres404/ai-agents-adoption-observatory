import json
from contextlib import contextmanager
import requests
from src.utils.aidedev_query import dataset_connection, prepare_catalog, iter_catalog


from src.utils.error_log import log_error
from src.utils.extraction_window import resolve_window, require_annual_window
from src.utils.extraction_evidence import log_source_execution, raw_output_path
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR, ROOT_DIR
from src.utils.time_utils import now_local, to_ec_naive


SOURCE_DIR = ROOT_DIR / "data" / "manual" / "aidedev_ai_coding"
PR_FILE = SOURCE_DIR / "all_pull_request.parquet"
REPO_FILE = SOURCE_DIR / "all_repository.parquet"
USER_FILE = SOURCE_DIR / "all_user.parquet"


SOURCE_START_DATE = "2023-01-01"
SOURCE_END_DATE = "2026-12-31"


ZENODO_BASE_URL = "https://zenodo.org/api/records/16919272/files/{}/content"


def _download_file(filename, destination):
    url = ZENODO_BASE_URL.format(filename)
    global_logger.info(f"Descargando {filename} desde Zenodo (puede tardar por el tamaño)...")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(destination, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        global_logger.info(f"✅ {filename} descargado exitosamente.")
    except Exception as e:
        if destination.exists():
            destination.unlink() # Borrar archivo corrupto
        raise Exception(f"Error descargando {filename}: {e}")


def _require_files():
    # A consolidated snapshot must not silently fall back to an older Zenodo
    # release or omit its supplemental tables when a local file goes missing.
    manifest_path = PR_FILE.parent / "dataset_manifest.json"
    if manifest_path.is_file():
        expected = _input_files().values()
        missing = [str(path) for path in expected if not path.is_file()]
        if missing:
            raise FileNotFoundError("Incomplete consolidated AIDev snapshot: " + ", ".join(missing))
        return
    files_to_check = {
        "all_pull_request.parquet": PR_FILE,
        "all_repository.parquet": REPO_FILE,
        "all_user.parquet": USER_FILE
    }
    for filename, path in files_to_check.items():
        if not path.exists():
            global_logger.warning(f"⚠️ Archivo faltante: {path.name}. Iniciando descarga automática...")
            _download_file(filename, path)


def _input_files():
    return {
        "prs": PR_FILE, "repos": REPO_FILE, "users": USER_FILE,
        "reviews": PR_FILE.parent / "pr_reviews.parquet",
        "tasks": PR_FILE.parent / "pr_task_type.parquet",
    }


@contextmanager
def _catalog(max_pr_rows=None, start_date=None, end_date=None, annual=False):
    window = resolve_window(start_date, end_date, default_start=SOURCE_START_DATE, default_end=SOURCE_END_DATE)
    if annual:
        require_annual_window(window)
    _require_files()
    # Labels observed in the consolidated snapshot: OpenAI_Codex, Copilot,
    # Claude_Code, Cursor, Google_Jules and Devin. Every dataset label must map
    # to an official name or ``valid_agents`` silently drops its PR rows.
    agent_mapping = {
        "OpenAI_Codex": "Codex", "Copilot": "GitHub Copilot Coding Agent",
        "Claude_Code": "Claude Code", "Google_Jules": "Google Jules",
        "Cursor": "Cursor Agent",
    }
    valid_agents = ["Codex", "GitHub Copilot Coding Agent", "Cursor Agent", "Windsurf Cascade", "Devin", "OpenCode", "Claude Code", "Cline", "Google Antigravity", "Google Jules"]
    with dataset_connection(PR_FILE.parent / ".work") as con:
        stats = prepare_catalog(con, _input_files(), agent_mapping, valid_agents,
                                window.start.isoformat(), window.end.isoformat(), max_pr_rows, annual=annual)
        yield iter_catalog(con, stats["unique_users"]), stats


def build_aidedev_catalog(max_pr_rows=None, start_date=None, end_date=None, annual=False):
    """Compatibility helper for small consumers; production streams instead."""
    with _catalog(max_pr_rows, start_date, end_date, annual=annual) as (records, stats):
        return list(records), stats


def extract_aidedev_catalog(run_id=None, start_date=None, end_date=None):
    """Project Parquet columns, aggregate on disk, publish JSON atomically."""
    global_logger.info("Iniciando AIDev desde Parquet con memoria acotada...")
    window = resolve_window(start_date, end_date, default_start=SOURCE_START_DATE, default_end=SOURCE_END_DATE)
    temporary = None
    try:
        with _catalog(start_date=window.start, end_date=window.end, annual=True) as (records, stats):
            out_path = raw_output_path("catalogo", prefix="aidedev", run_id=run_id, raw_dir=RAW_DIR)
            temporary = out_path.with_suffix(".json.tmp")
            metadata = {
                "source": "catalogo", "dataset": "AIDev Dataset: AI Coding",
                "input_files": [str(p) for p in _input_files().values() if p.is_file()],
                "stats": stats, "date_range_start": window.start.isoformat(),
                "date_range_end": window.end.isoformat(),
                "grain": "agent_repository_year",
                "date_basis": "PR creation year (UTC); other metrics are snapshot attributes",
                "task_confidence_scale": "Original annotation scale; not an adoption index",
                "extracted_at": to_ec_naive(now_local()).isoformat(),
            }
            manifest_path = PR_FILE.parent / "dataset_manifest.json"
            if manifest_path.is_file():
                metadata["dataset_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write('{"metadata":')
                json.dump(metadata, handle, ensure_ascii=False, allow_nan=False)
                handle.write(',"items":[\n')
                count = 0
                for record in records:
                    if count:
                        handle.write(",")
                    json.dump(record, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                    handle.write("\n")
                    count += 1
                handle.write("]}")
            if count != stats["records_generated"]:
                raise RuntimeError("AIDev catalog count does not match aggregation")
            temporary.replace(out_path)
        return log_source_execution("catalogo", "success" if count else "empty", count,
                                    None, str(SOURCE_DIR), out_path,
                                    notes="AIDev projected Parquet aggregation", run_id=run_id)
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        log_error("aidedev", type(exc).__name__, str(exc), "Extractor abortado", run_id=run_id)
        global_logger.error(f"Fallo en extractor AIDev: {exc}")
        return log_source_execution("catalogo", "failed", 0, None, str(SOURCE_DIR), notes=str(exc), run_id=run_id)


if __name__ == "__main__":
    result = extract_aidedev_catalog()
    raise SystemExit(0 if result.status.value in {"success", "empty"} else 1)
