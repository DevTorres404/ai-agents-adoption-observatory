"""Source boundaries shared by independent workers and explicit maintenance."""
from contextlib import contextmanager

from sqlalchemy import text

from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.observatory_scope import ACTIVE_SOURCES, INACTIVE_SOURCES

PIPELINES = ("main", "all", *sorted(ACTIVE_SOURCES))
RETIRED_SOURCES = INACTIVE_SOURCES
# Both workers share Staging/Gold dimensions and legacy evidence pointers.
PROCESSING_LOCK_ID = 719260916


def validate_pipeline(pipeline):
    if pipeline not in PIPELINES:
        raise ValueError(f"Unknown pipeline: {pipeline!r}")
    return pipeline


def includes_source(pipeline, source):
    validate_pipeline(pipeline)
    if source not in ACTIVE_SOURCES:
        return False
    return pipeline == "all" or (pipeline == "main" and source != "github") or pipeline == source


def source_predicate(pipeline, column="f.fuente"):
    """Only internal column names and validated profiles, never user SQL."""
    validate_pipeline(pipeline)
    if column not in {"f.fuente", "s.fuente", "fuente"}:
        raise ValueError("Unsupported source column")
    owned = sorted(source for source in ACTIVE_SOURCES if includes_source(pipeline, source))
    literals = ", ".join("'" + source.replace("'", "''") + "'" for source in owned)
    return f"{column} IN ({literals})"


@contextmanager
def processing_lock(run_id):
    """Serialize database publication, NOT slow external extraction.

    A dedicated session holds the lock across transactions in the existing
    loaders. Always release it before returning the connection to the pool.
    """
    if not db_connector.engine:
        raise RuntimeError("Processing lock requires PostgreSQL")
    with db_connector.engine.connect() as conn:
        try:
            global_logger.info(f"Waiting for ETL processing lock run_id={run_id}")
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": PROCESSING_LOCK_ID})
            conn.commit()
            yield
        finally:
            try:
                conn.rollback()
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": PROCESSING_LOCK_ID})
                conn.commit()
            except Exception:
                # Do not pool a session that might still own the lock.
                conn.invalidate()
                raise
