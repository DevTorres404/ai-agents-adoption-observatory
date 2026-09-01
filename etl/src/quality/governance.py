"""Run-scoped quality governance primitives.

The functions in this module are deliberately pure where possible so the same
snapshot can be verified without touching production data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd

from src.utils.extraction_evidence import (
    ExtractionResult,
    ExtractionStatus,
    _write_json_atomic,
)


SUCCESSFUL_ATTEMPTS = {
    ExtractionStatus.SUCCESS,
    ExtractionStatus.PARTIAL_SUCCESS,
    ExtractionStatus.EMPTY,
}
DEFAULT_NUMERIC_METRICS = (
    "cantidad_menciones",
    "cantidad_interacciones",
    "score_popularidad",
    "stars_github",
    "forks_github",
    "issues_abiertos",
    "releases",
    "indice_adopcion",
    "indice_innovacion",
    "sentimiento_promedio",
)


def _as_utc(value) -> datetime:
    # Guard against pd.NaT and None — both must be rejected before parsing.
    # bool(pd.NaT) is True in Python, so an `if value:` check is NOT safe here.
    if value is None or value is pd.NaT:
        raise ValueError(f"Cannot convert {value!r} to a UTC datetime")
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reconcile_quality_counts(raw_records, eligible_records, duplicates_removed, materialized_records):
    """Reconcile one run without treating intentional deduplication as error."""
    raw_records = max(int(raw_records or 0), 0)
    eligible_records = max(min(int(eligible_records or 0), raw_records), 0)
    duplicates_removed = max(min(int(duplicates_removed or 0), eligible_records), 0)
    expected = max(eligible_records - duplicates_removed, 0)
    materialized = max(int(materialized_records or 0), 0)
    load_errors = max(expected - materialized, 0)
    completion = 100.0 if expected == 0 else min(materialized / expected * 100.0, 100.0)
    error_rate = 0.0 if expected == 0 else load_errors / expected * 100.0
    dedup_rate = 0.0 if eligible_records == 0 else duplicates_removed / eligible_records * 100.0
    return {
        "total_raw_records": raw_records,
        "eligible_records": eligible_records,
        "total_duplicates_removed": duplicates_removed,
        "expected_staging_records": expected,
        "total_staging_records": materialized,
        "load_error_records": load_errors,
        "completion_rate": round(completion, 2),
        "overall_error_rate": round(error_rate, 2),
        "deduplication_rate": round(dedup_rate, 2),
    }


def build_source_freshness(
    run_id,
    results: Iterable[ExtractionResult],
    previous_success: Mapping[str, datetime] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
):
    """Build per-source freshness as-of a run.

    EMPTY is a completed successful attempt: it refreshes last_success_at while
    preserving records_extracted=0. A FAILED attempt retains prior success time.
    """
    now = _as_utc(now or datetime.now(timezone.utc))
    previous_success = previous_success or {}
    grouped: dict[str, list[ExtractionResult]] = {}
    for result in results:
        grouped.setdefault(result.source, []).append(result)

    rows = []
    for source, source_results in sorted(grouped.items()):
        ordered = sorted(source_results, key=lambda item: _as_utc(item.execution_timestamp or now))
        summaries = [item for item in ordered if item.query is None]
        latest = summaries[-1] if summaries else ordered[-1]
        attempts = [_as_utc(item.execution_timestamp or now) for item in ordered]
        successful = [
            _as_utc(item.execution_timestamp or now)
            for item in ordered
            if item.status in SUCCESSFUL_ATTEMPTS
        ]
        prior = previous_success.get(source)
        # Use explicit `is not None` — `if prior:` is unsafe because pd.NaT is truthy.
        last_success = max(successful) if successful else (_as_utc(prior) if prior is not None else None)
        age_hours = None if last_success is None else round(max((now - last_success).total_seconds(), 0) / 3600, 2)
        query_results = [item for item in ordered if item.query is not None]
        completed = sum(item.status in SUCCESSFUL_ATTEMPTS for item in query_results)
        records_basis = summaries if summaries else query_results or ordered
        rows.append({
            "run_id": run_id,
            "source": source,
            "latest_status": latest.status.value,
            "records_extracted": sum(item.records_extracted for item in records_basis),
            "last_attempt_at": max(attempts),
            "last_success_at": last_success,
            "age_hours": age_hours,
            "is_stale": last_success is None or age_hours > float(stale_after_hours),
            "expected_queries": len(query_results) or None,
            "completed_queries": completed if query_results else None,
        })
    return rows


def _covered(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    return ~normalized.isin({"", "n/a", "na", "none", "unknown", "otro", "sin clasificar"})


def calculate_semantic_coverage(frame: pd.DataFrame, run_id, thresholds: Mapping[str, float]):
    dimensions = {
        "platform": "dim_nombre_plataforma",
        "technology": "dim_nombre_tecnologia",
        "community": "dim_nombre_comunidad",
        "llm": "llm_confianza",
    }
    if frame.empty or "fuente" not in frame:
        return []

    rows = []
    for source, source_frame in frame.groupby("fuente", dropna=False):
        total = len(source_frame)
        for dimension, column in dimensions.items():
            if column not in source_frame:
                covered = 0
            elif dimension == "llm":
                covered = int((pd.to_numeric(source_frame[column], errors="coerce").fillna(0) > 0).sum())
            else:
                covered = int(_covered(source_frame[column]).sum())
            percentage = round(covered / total * 100, 2) if total else 0.0
            threshold = float(thresholds.get(dimension, 0))
            rows.append({
                "run_id": run_id,
                "source": str(source),
                "dimension": dimension,
                "total_count": total,
                "covered_count": covered,
                "coverage_pct": percentage,
                "threshold_pct": threshold,
                "warning": bool(total and percentage < threshold),
                "enforcement_mode": "warning_only",
            })
    return rows


def build_stratified_sample(frame: pd.DataFrame, run_id, seed: str, per_stratum: int):
    if frame.empty:
        return []
    candidates = frame.copy()
    for column in ("fuente", "nombre_agente", "titulo", "url"):
        if column not in candidates:
            candidates[column] = ""
    if "raw_record_id" not in candidates:
        candidates["raw_record_id"] = None

    def stable_key(row):
        lineage = row["raw_record_id"]
        if pd.isna(lineage):
            lineage = f"{row['fuente']}|{row['nombre_agente']}|{row['titulo']}|{row['url']}"
        return hashlib.sha256(f"{seed}|{lineage}".encode("utf-8")).hexdigest()

    candidates["_sample_key"] = candidates.apply(stable_key, axis=1)
    selected = (
        candidates.sort_values(["fuente", "nombre_agente", "_sample_key"], kind="mergesort")
        .groupby(["fuente", "nombre_agente"], dropna=False, sort=True)
        .head(max(int(per_stratum), 0))
    )
    rows = []
    for _, row in selected.iterrows():
        raw_record_id = None if pd.isna(row["raw_record_id"]) else int(row["raw_record_id"])
        rows.append({
            "run_id": run_id,
            "sample_seed": seed,
            "source": str(row["fuente"]),
            "agent": str(row["nombre_agente"]),
            "raw_record_id": raw_record_id,
            "sample_key": row["_sample_key"],
            "title": str(row["titulo"] or ""),
            "url": str(row["url"] or ""),
            "label": None,
            "reviewer": None,
            "reviewed_at": None,
        })
    return rows


def build_source_metrics(frame: pd.DataFrame, run_id, metrics: Sequence[str] = DEFAULT_NUMERIC_METRICS):
    """Normalize each signal independently within its own source."""
    if frame.empty or not {"fuente", "nombre_agente"}.issubset(frame.columns):
        return []
    rows = []
    for metric in metrics:
        if metric not in frame:
            continue
        working = frame[["fuente", "nombre_agente", metric]].copy()
        working[metric] = pd.to_numeric(working[metric], errors="coerce")
        grouped = working.dropna(subset=[metric]).groupby(["fuente", "nombre_agente"], as_index=False)[metric].mean()
        for source, source_frame in grouped.groupby("fuente"):
            minimum = float(source_frame[metric].min())
            maximum = float(source_frame[metric].max())
            denominator = maximum - minimum
            for _, item in source_frame.sort_values("nombre_agente").iterrows():
                value = float(item[metric])
                normalized = 0.0 if denominator == 0 else (value - minimum) / denominator
                rows.append({
                    "run_id": run_id,
                    "source": str(source),
                    "agent": str(item["nombre_agente"]),
                    "metric_name": metric,
                    "raw_value": value,
                    "normalization_method": "min_max_within_source_metric",
                    "normalized_value": round(normalized, 6),
                })
    return sorted(rows, key=lambda item: (item["source"], item["metric_name"], item["agent"]))


@dataclass(frozen=True)
class QualityPublication:
    run_id: str
    status: ExtractionStatus
    run_directory: Path
    marker_file: Path


def _write_frame_atomic(destination: Path, frame: pd.DataFrame):
    from src.utils.extraction_evidence import _atomic_write

    _atomic_write(destination, lambda stream: frame.to_csv(stream, index=False))


def publish_quality_evidence(run_id, tables: Mapping[str, pd.DataFrame], status, evidence_root: Path, legacy_root: Path):
    final_status = ExtractionStatus(status)
    safe_run_id = "".join(char if char.isalnum() or char in "_.-" else "_" for char in str(run_id))
    run_directory = Path(evidence_root) / safe_run_id
    published = {}
    for name, frame in sorted(tables.items()):
        destination = run_directory / f"{name}.csv"
        _write_frame_atomic(destination, frame)
        published[name] = str(destination).replace("\\", "/")

    marker = run_directory / "quality_summary.json"
    _write_json_atomic(marker, {
        "run_id": str(run_id),
        "status": final_status.value,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "files": published,
    })

    if final_status in {ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL_SUCCESS}:
        legacy_root = Path(legacy_root)
        for name, frame in sorted(tables.items()):
            _write_frame_atomic(legacy_root / f"{name}.csv", frame)
        _write_json_atomic(legacy_root / "quality_latest.json", {
            "run_id": str(run_id),
            "status": final_status.value,
            "marker_file": str(marker).replace("\\", "/"),
        })

    return QualityPublication(str(run_id), final_status, run_directory, marker)
