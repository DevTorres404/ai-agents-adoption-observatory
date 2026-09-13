"""Keep unit tests out of production logs, evidence, networks and databases."""
import logging
import os
import socket

import pytest

logger = logging.getLogger("pipeline_logger")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
logger.propagate = False


@pytest.fixture(autouse=True)
def isolate_unit_test_artifacts(monkeypatch, tmp_path):
    from src.utils import error_log
    from src.loaders import load_raw_to_db
    monkeypatch.setattr(error_log, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(load_raw_to_db, "ROOT_DIR", tmp_path)
    if os.getenv("ETL_POSTGRES_INTEGRATION") != "1":
        from src.utils.db import db_connector
        monkeypatch.setattr(db_connector, "engine", None)

        def offline(*args, **kwargs):
            raise RuntimeError("Unit tests must not access the network")
        monkeypatch.setattr(socket.socket, "connect", offline)
