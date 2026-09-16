"""Source boundaries shared by the two ETLs and explicit global maintenance."""
from contextlib import contextmanager

from sqlalchemy import text

from src.utils.db import db_connector
from src.utils.logger import global_logger

PIPELINES = ("main", "github", "all")
RETIRED_SOURCES = frozenset({"fuente_propia", "encuesta"})
# Both workers share Staging/Gold dimensions and legacy evidence pointers.
PROCESSING_LOCK_ID = 719260916


def validate_pipeline(pipeline):
    if pipeline not in PIPELINES:
        raise ValueError(f"Unknown pipeline: {pipeline!r}")
    return pipeline


def includes_source(pipeline, source):
    validate_pipeline(pipeline)
    if source in RETIRED_SOURCES:
        return False
    return pipeline == "all" or (source == "github") == (pipeline == "github")


def source_predicate(pipeline, column="f.fuente"):
    """Only internal column names and validated profiles, never user SQL."""
    validate_pipeline(pipeline)
    if column not in {"f.fuente", "s.fuente", "fuente"}:
        raise ValueError("Unsupported source column")
    if pipeline == "all":
        return f"COALESCE({column}, '') NOT IN ('fuente_propia', 'encuesta')"
    if pipeline == "github":
        return f"{column} = 'github'"
    return f"COALESCE({column}, '') NOT IN ('github', 'fuente_propia', 'encuesta')"


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
