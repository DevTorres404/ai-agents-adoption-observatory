import datetime
import json
from pathlib import Path
import requests

import pandas as pd

from src.utils.error_log import log_error
from src.utils.extraction_evidence import log_source_execution
from src.utils.logger import global_logger
from src.utils.paths import RAW_DIR, ROOT_DIR


SOURCE_DIR = ROOT_DIR / "data" / "manual" / "aidedev_ai_coding"
PR_FILE = SOURCE_DIR / "all_pull_request.parquet"
REPO_FILE = SOURCE_DIR / "all_repository.parquet"
USER_FILE = SOURCE_DIR / "all_user.parquet"
DATA_TABLE_FILE = SOURCE_DIR / "data_table.md"

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
    files_to_check = {
        "all_pull_request.parquet": PR_FILE,
        "all_repository.parquet": REPO_FILE,
        "all_user.parquet": USER_FILE,
        "data_table.md": DATA_TABLE_FILE
    }
    for filename, path in files_to_check.items():
        if not path.exists():
            global_logger.warning(f"⚠️ Archivo faltante: {path.name}. Iniciando descarga automática...")
            _download_file(filename, path)


def _safe_text(value):
    if pd.isna(value):
        return ""
    return str(value)


def build_aidedev_catalog(max_pr_rows=None):
    """
    Builds an analytical catalog from the AIDev Parquet dataset.
    The raw Parquet files remain untouched in data/manual/aidedev_ai_coding.
    """
    _require_files()
    global_logger.info("Leyendo AIDev Dataset: AI Coding desde Parquet...")

    pr_columns = [
        "id",
        "title",
        "body",
        "agent",
        "user_id",
        "user",
        "state",
        "created_at",
        "closed_at",
        "merged_at",
        "repo_id",
        "repo_url",
        "html_url",
    ]
    repo_columns = ["id", "url", "license", "full_name", "language", "forks", "stars"]
    user_columns = ["id", "login", "followers", "following", "created_at"]

    pull_requests = pd.read_parquet(PR_FILE, columns=pr_columns)
    if max_pr_rows:
        pull_requests = pull_requests.head(max_pr_rows)

    repositories = pd.read_parquet(REPO_FILE, columns=repo_columns)
    users = pd.read_parquet(USER_FILE, columns=user_columns)

    pull_requests["created_at"] = pd.to_datetime(pull_requests["created_at"], errors="coerce", utc=True)
    pull_requests["merged_at"] = pd.to_datetime(pull_requests["merged_at"], errors="coerce", utc=True)
    start_date = pd.Timestamp(SOURCE_START_DATE, tz="UTC")
    end_date = pd.Timestamp(SOURCE_END_DATE, tz="UTC")
    pull_requests = pull_requests[
        (pull_requests["created_at"] >= start_date)
        & (pull_requests["created_at"] <= end_date)
    ]
    pull_requests["is_merged"] = pull_requests["merged_at"].notna().astype(int)

    grouped = (
        pull_requests
        .groupby(["agent", "repo_id", "repo_url"], dropna=False)
        .agg(
            pull_requests_count=("id", "count"),
            merged_pull_requests=("is_merged", "sum"),
            unique_contributors=("user_id", "nunique"),
            first_activity=("created_at", "min"),
            last_activity=("created_at", "max"),
            sample_pr_title=("title", "first"),
            sample_pr_url=("html_url", "first"),
        )
        .reset_index()
    )

    repositories = repositories.rename(columns={"id": "repo_id", "url": "repo_api_url"})
    enriched = grouped.merge(repositories, on="repo_id", how="left")
    total_users = int(users["id"].count()) if "id" in users.columns else int(len(users))

    records = []
    for _, row in enriched.iterrows():
        pull_requests_count = int(row.get("pull_requests_count") or 0)
        merged_pull_requests = int(row.get("merged_pull_requests") or 0)
        merge_rate = round(merged_pull_requests / pull_requests_count, 4) if pull_requests_count else 0.0
        first_activity = row.get("first_activity")
        last_activity = row.get("last_activity")

        records.append({
            "id": f"{_safe_text(row.get('agent'))}:{_safe_text(row.get('repo_id'))}",
            "agent": _safe_text(row.get("agent")),
            "repo_id": None if pd.isna(row.get("repo_id")) else int(row.get("repo_id")),
            "repo_url": _safe_text(row.get("repo_url")),
            "repo_api_url": _safe_text(row.get("repo_api_url")),
            "full_name": _safe_text(row.get("full_name")),
            "language": _safe_text(row.get("language")),
            "license": _safe_text(row.get("license")),
            "stars": 0 if pd.isna(row.get("stars")) else int(row.get("stars")),
            "forks": 0 if pd.isna(row.get("forks")) else int(row.get("forks")),
            "pull_requests_count": pull_requests_count,
            "merged_pull_requests": merged_pull_requests,
            "merge_rate": merge_rate,
            "unique_contributors": int(row.get("unique_contributors") or 0),
            "first_activity": None if pd.isna(first_activity) else first_activity.isoformat(),
            "last_activity": None if pd.isna(last_activity) else last_activity.isoformat(),
            "sample_pr_title": _safe_text(row.get("sample_pr_title")),
            "sample_pr_url": _safe_text(row.get("sample_pr_url")),
            "dataset": "AIDev Dataset: AI Coding",
            "total_users_dataset": total_users,
        })

    records = sorted(records, key=lambda item: item["pull_requests_count"], reverse=True)
    return records, {
        "pull_request_rows_read": int(len(pull_requests)),
        "repository_rows_read": int(len(repositories)),
        "user_rows_read": int(len(users)),
        "records_generated": int(len(records)),
    }


def extract_aidedev_catalog():
    global_logger.info("Iniciando extraccion estructurada AIDev Dataset: AI Coding...")
    try:
        records, stats = build_aidedev_catalog()
    except Exception as exc:
        log_error("aidedev_catalog", type(exc).__name__, str(exc), "Extractor abortado")
        log_source_execution("catalogo", "failed", 0, None, str(SOURCE_DIR), notes=str(exc))
        global_logger.error(f"Fallo en extractor AIDev: {exc}")
        return

    date_stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RAW_DIR / "archivos" / "catalogo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"aidedev_{date_stamp}.json"

    payload = {
        "metadata": {
            "source": "catalogo",
            "dataset": "AIDev Dataset: AI Coding",
            "input_files": [
                str(PR_FILE.relative_to(ROOT_DIR)).replace("\\", "/"),
                str(REPO_FILE.relative_to(ROOT_DIR)).replace("\\", "/"),
                str(USER_FILE.relative_to(ROOT_DIR)).replace("\\", "/"),
            ],
            "stats": stats,
            "date_range_start": SOURCE_START_DATE,
            "date_range_end": SOURCE_END_DATE,
            "extracted_at": datetime.datetime.now().isoformat(),
        },
        "items": records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global_logger.info(f"AIDev catalog generado: {len(records)} registros en {out_path.name}")
    log_source_execution("catalogo", "success", len(records), None, str(SOURCE_DIR), out_path, notes="AIDev Dataset: AI Coding")


if __name__ == "__main__":
    extract_aidedev_catalog()
