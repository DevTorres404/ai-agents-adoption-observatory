import csv
import datetime
import json
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from src.utils.logger import global_logger
from src.utils.paths import ROOT_DIR


EVIDENCE_FILE = ROOT_DIR / "docs" / "evidencias" / "source_execution_evidence.csv"
EVIDENCE_RUNS_DIR = ROOT_DIR / "docs" / "evidencias" / "runs"
EVIDENCE_FIELDS = (
    "execution_timestamp",
    "run_id",
    "source",
    "query",
    "status",
    "records_extracted",
    "http_status",
    "url",
    "raw_path",
    "notes",
)


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    EMPTY = "empty"
    FAILED = "failed"


@dataclass(frozen=True)
class ExtractionResult:
    source: str
    status: ExtractionStatus
    records_extracted: int = 0
    http_status: Optional[int] = None
    url: Optional[str] = None
    raw_path: Optional[str] = None
    notes: Optional[str] = None
    run_id: Optional[str] = None
    query: Optional[str] = None
    execution_timestamp: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "status", ExtractionStatus(self.status))
        object.__setattr__(self, "records_extracted", int(self.records_extracted or 0))
        if self.records_extracted < 0:
            raise ValueError("records_extracted cannot be negative")
        if not self.source:
            raise ValueError("source is required")

    def as_row(self):
        return {
            "execution_timestamp": self.execution_timestamp or "",
            "run_id": self.run_id or "",
            "source": self.source,
            "query": self.query or "",
            "status": self.status.value,
            "records_extracted": self.records_extracted,
            "http_status": "" if self.http_status is None else self.http_status,
            "url": self.url or "",
            "raw_path": str(self.raw_path).replace("\\", "/") if self.raw_path else "",
            "notes": self.notes or "",
        }


def aggregate_status(results: Iterable[ExtractionResult]) -> ExtractionStatus:
    results = list(results)
    if not results:
        return ExtractionStatus.EMPTY

    statuses = {ExtractionStatus(result.status) for result in results}
    useful_data = any(
        result.records_extracted > 0
        or result.status in {ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL_SUCCESS}
        for result in results
    )
    has_incident = bool(
        statuses & {ExtractionStatus.FAILED, ExtractionStatus.PARTIAL_SUCCESS}
    )

    if has_incident:
        return ExtractionStatus.PARTIAL_SUCCESS if useful_data else ExtractionStatus.FAILED
    if useful_data:
        return ExtractionStatus.SUCCESS
    return ExtractionStatus.EMPTY


@dataclass(frozen=True)
class EvidencePublication:
    run_id: str
    status: ExtractionStatus
    evidence_file: Path
    summary_file: Path
    legacy_file: Path


def _atomic_write(destination: Path, write):
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".tmp",
        prefix=f".{destination.name}.",
        dir=destination.parent,
        delete=False,
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            write(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _write_csv_atomic(destination: Path, rows):
    def write(stream):
        writer = csv.DictWriter(stream, fieldnames=EVIDENCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    _atomic_write(destination, write)


def _write_json_atomic(destination: Path, payload):
    def write(stream):
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    _atomic_write(destination, write)


class EvidenceRun:
    def __init__(self, run_id, evidence_root=EVIDENCE_RUNS_DIR, legacy_file=EVIDENCE_FILE):
        if run_id is None or str(run_id).strip() == "":
            raise ValueError("run_id is required for run-scoped evidence")
        self.run_id = str(run_id)
        self.evidence_root = Path(evidence_root)
        self.legacy_file = Path(legacy_file)
        self.results = []

    @property
    def run_directory(self):
        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.run_id)
        return self.evidence_root / safe_run_id

    def record(self, result: ExtractionResult):
        result_run_id = str(result.run_id) if result.run_id is not None else None
        if result_run_id not in {None, self.run_id}:
            raise ValueError(
                f"Evidence result run_id {result_run_id!r} does not match active run {self.run_id!r}"
            )
        timestamp = result.execution_timestamp or datetime.datetime.now().isoformat(timespec="seconds")
        scoped_result = replace(result, run_id=self.run_id, execution_timestamp=timestamp)
        self.results.append(scoped_result)
        return scoped_result

    def publish(self, status=None):
        final_status = ExtractionStatus(status) if status else aggregate_status(self.results)
        rows = [result.as_row() for result in self.results]
        run_directory = self.run_directory
        evidence_file = run_directory / "evidence.csv"
        summary_file = run_directory / "summary.json"
        summary_results = [result for result in self.results if result.query is None]
        if not summary_results:
            summary_results = self.results
        summary = {
            "run_id": self.run_id,
            "status": final_status.value,
            "published_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "event_count": len(self.results),
            "records_extracted": sum(item.records_extracted for item in summary_results),
        }

        _write_csv_atomic(evidence_file, rows)
        # summary.json is the publication marker and is replaced last.
        _write_json_atomic(summary_file, summary)

        if final_status in {ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL_SUCCESS}:
            _write_csv_atomic(self.legacy_file, rows)
            _write_json_atomic(
                self.legacy_file.with_name("source_execution_evidence_latest.json"),
                {
                    "run_id": self.run_id,
                    "status": final_status.value,
                    "evidence_file": str(evidence_file).replace("\\", "/"),
                },
            )

        return EvidencePublication(
            run_id=self.run_id,
            status=final_status,
            evidence_file=evidence_file,
            summary_file=summary_file,
            legacy_file=self.legacy_file,
        )


_ACTIVE_EVIDENCE_RUN = ContextVar("active_evidence_run", default=None)


def current_evidence_run():
    return _ACTIVE_EVIDENCE_RUN.get()


@contextmanager
def evidence_context(run: EvidenceRun):
    token = _ACTIVE_EVIDENCE_RUN.set(run)
    try:
        yield run
    finally:
        _ACTIVE_EVIDENCE_RUN.reset(token)


def new_local_run_id():
    timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"local-{timestamp}-{uuid.uuid4().hex[:8]}"


def raw_output_path(source, prefix=None, run_id=None, now=None, raw_dir=None):
    active_run = current_evidence_run()
    effective_run_id = (
        run_id if run_id is not None
        else (active_run.run_id if active_run else new_local_run_id())
    )
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(effective_run_id))
    timestamp = (now or datetime.datetime.now()).strftime("%Y-%m-%dT%H%M%S%f")
    source_dir = Path(raw_dir or (ROOT_DIR / "data" / "raw")) / source
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir / f"{prefix or source}_{timestamp}_{safe_run_id}.json"


def log_source_execution(
    source,
    status,
    records_extracted=0,
    http_status=None,
    url=None,
    raw_path=None,
    notes=None,
    run_id=None,
    query=None,
):
    """Record one source or work-unit outcome in the active run."""
    active_run = current_evidence_run()
    effective_run_id = str(run_id) if run_id is not None else None
    if active_run is not None:
        effective_run_id = effective_run_id or active_run.run_id

    result = ExtractionResult(
        source=source,
        status=ExtractionStatus(status),
        records_extracted=records_extracted,
        http_status=http_status,
        url=url,
        raw_path=str(raw_path) if raw_path else None,
        notes=notes,
        run_id=effective_run_id,
        query=query,
        execution_timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
    )

    if active_run is not None:
        result = active_run.record(result)
    else:
        standalone_run = EvidenceRun(effective_run_id or new_local_run_id())
        result = standalone_run.record(result)
        standalone_run.publish()

    global_logger.info(
        f"Evidencia fuente {source}: run_id={result.run_id}, query={query}, "
        f"status={result.status.value}, records={records_extracted}, http={http_status}"
    )
    return result
