"""
Tests for el loader raw-to-db: atomicidad de la transacción y run_id.

Task 2A: Verifica que metadata de archivo y records se committean en una sola transacción.
Task 2B: Verifica que run_loader acepta run_id y lo incluye en los inserts.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.loaders.load_raw_to_db import run_loader


def _make_mock_conn(execute_side_effect):
    """Crea mock_conn con begin() que trackea commits de la transacción."""
    committed = []

    class FakeTrans:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                committed.append(True)
            return False

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.begin = lambda: FakeTrans()
    mock_conn.execute = execute_side_effect

    return mock_conn, committed


def _execute_for_file_load(file_id_value=1):
    """Factory de execute mock para un file load exitoso o con records fallidos."""
    records_inserted = []

    def mock_execute(query_obj, params=None):
        query_str = str(query_obj)
        if "SELECT" in query_str:
            result = MagicMock()
            result.fetchone.return_value = None
            return result
        elif "RETURNING" in query_str:
            result = MagicMock()
            result.scalar.return_value = file_id_value
            return result
        else:
            records_inserted.append(params)
            return MagicMock()

    return mock_execute, records_inserted


class RawLoaderApprovalTest(unittest.TestCase):
    """Verifica el comportamiento del loader post-fix."""

    def test_record_insert_failure_aborts_entire_transaction(self):
        """
        POST-FIX: Si la inserción de records falla, la transacción completa se revierte.
        El hash del archivo NO queda huérfano en raw_files (poison pill eliminado).
        """
        file_id_value = 99

        def mock_execute(query_obj, params=None):
            query_str = str(query_obj)
            if "SELECT" in query_str:
                result = MagicMock()
                result.fetchone.return_value = None
                return result
            elif "RETURNING" in query_str:
                result = MagicMock()
                result.scalar.return_value = file_id_value
                return result
            else:
                raise ValueError("Fallo al insertar records")

        mock_conn, committed = _make_mock_conn(mock_execute)

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.json").write_text("{}", encoding="utf-8")

            engine = MagicMock()
            engine.connect.return_value = mock_conn
            mock_connector = MagicMock()
            mock_connector.engine = engine

            with (
                patch("src.loaders.load_raw_to_db.db_connector", mock_connector),
                patch("src.loaders.load_raw_to_db.RAW_DIR", raw_dir),
                patch("src.loaders.load_raw_to_db.calculate_sha256", return_value="abc123"),
                patch("src.loaders.load_raw_to_db.extract_metadata", return_value={
                    "fuente": "test", "tipo_fuente": "test",
                    "ruta_relativa": "test.json", "nombre_archivo": "test.json",
                    "tamano_bytes": 2, "cantidad_registros": 1, "cantidad_columnas": 0,
                    "records": [{"key": "value"}],
                }),
                patch("src.loaders.load_raw_to_db.log_error"),
            ):
                run_loader()

        # Post-fix: transacción revierta — NO se confirma commit
        self.assertEqual(len(committed), 0)

    def test_no_commit_when_metadata_extraction_fails(self):
        """Si extract_metadata falla, no se intenta commit."""
        mock_conn, committed = _make_mock_conn(MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.json").write_text("{}", encoding="utf-8")

            engine = MagicMock()
            engine.connect.return_value = mock_conn
            mock_connector = MagicMock()
            mock_connector.engine = engine

            with (
                patch("src.loaders.load_raw_to_db.db_connector", mock_connector),
                patch("src.loaders.load_raw_to_db.RAW_DIR", raw_dir),
                patch("src.loaders.load_raw_to_db.calculate_sha256", return_value="abc123"),
                patch("src.loaders.load_raw_to_db.extract_metadata",
                       side_effect=RuntimeError("parse error")),
                patch("src.loaders.load_raw_to_db.log_error"),
            ):
                run_loader()

        self.assertEqual(len(committed), 0)


class RawLoaderAtomicityTest(unittest.TestCase):
    """Verifica atomicidad post-fix: metadata y records en la misma transacción."""

    def test_record_failure_rolls_back_file_metadata(self):
        """
        Si la inserción de records falla, el metadata del archivo NO debe ser commiteado.
        Post-fix: ambas operaciones están en la misma transacción.
        """
        file_id_value = 42

        def mock_execute(query_obj, params=None):
            query_str = str(query_obj)
            if "SELECT" in query_str:
                result = MagicMock()
                result.fetchone.return_value = None
                return result
            elif "RETURNING" in query_str:
                result = MagicMock()
                result.scalar.return_value = file_id_value
                return result
            else:
                raise ValueError("Fallo al insertar records")

        mock_conn, committed = _make_mock_conn(mock_execute)

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.json").write_text("{}", encoding="utf-8")

            engine = MagicMock()
            engine.connect.return_value = mock_conn
            mock_connector = MagicMock()
            mock_connector.engine = engine

            with (
                patch("src.loaders.load_raw_to_db.db_connector", mock_connector),
                patch("src.loaders.load_raw_to_db.RAW_DIR", raw_dir),
                patch("src.loaders.load_raw_to_db.calculate_sha256", return_value="abc123"),
                patch("src.loaders.load_raw_to_db.extract_metadata", return_value={
                    "fuente": "test", "tipo_fuente": "test",
                    "ruta_relativa": "test.json", "nombre_archivo": "test.json",
                    "tamano_bytes": 2, "cantidad_registros": 2, "cantidad_columnas": 1,
                    "records": [{"key": "a"}, {"key": "b"}],
                }),
                patch("src.loaders.load_raw_to_db.log_error"),
            ):
                run_loader()

        # Post-fix: si records fallan, la transacción NO se confirma
        self.assertEqual(len(committed), 0)

    def test_successful_load_single_commit(self):
        """Un load exitoso debe usar exactamente UNA transacción confirmada."""
        mock_execute, records_inserted = _execute_for_file_load(file_id_value=1)
        mock_conn, committed = _make_mock_conn(mock_execute)

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.json").write_text("{}", encoding="utf-8")

            engine = MagicMock()
            engine.connect.return_value = mock_conn
            mock_connector = MagicMock()
            mock_connector.engine = engine

            with (
                patch("src.loaders.load_raw_to_db.db_connector", mock_connector),
                patch("src.loaders.load_raw_to_db.RAW_DIR", raw_dir),
                patch("src.loaders.load_raw_to_db.calculate_sha256", return_value="abc123"),
                patch("src.loaders.load_raw_to_db.extract_metadata", return_value={
                    "fuente": "test", "tipo_fuente": "test",
                    "ruta_relativa": "test.json", "nombre_archivo": "test.json",
                    "tamano_bytes": 2, "cantidad_registros": 2, "cantidad_columnas": 1,
                    "records": [{"key": "a"}, {"key": "b"}],
                }),
                patch("src.loaders.load_raw_to_db.log_error"),
            ):
                run_loader()

        self.assertEqual(len(records_inserted), 2)
        self.assertEqual(len(committed), 1)


class RawLoaderRunIdContractTest(unittest.TestCase):
    """Task 2B: Verifica que run_loader acepta e incluye run_id."""

    def test_run_loader_accepts_run_id_parameter(self):
        """run_loader debe aceptar run_id como parámetro."""
        import inspect
        sig = inspect.signature(run_loader)
        self.assertIn("run_id", sig.parameters)

    def test_run_id_appears_in_file_insert_sql(self):
        """El run_id debe incluirse en el INSERT de raw_files."""
        captured_queries = []

        def mock_execute(query_obj, params=None):
            query_str = str(query_obj)
            captured_queries.append({"sql": query_str, "params": params})
            result = MagicMock()
            if "SELECT" in query_str:
                result.fetchone.return_value = None
            elif "RETURNING" in query_str:
                result.scalar.return_value = 1
            return result

        mock_conn, _ = _make_mock_conn(mock_execute)

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "raw"
            raw_dir.mkdir()
            (raw_dir / "test.json").write_text("{}", encoding="utf-8")

            engine = MagicMock()
            engine.connect.return_value = mock_conn
            mock_connector = MagicMock()
            mock_connector.engine = engine

            with (
                patch("src.loaders.load_raw_to_db.db_connector", mock_connector),
                patch("src.loaders.load_raw_to_db.RAW_DIR", raw_dir),
                patch("src.loaders.load_raw_to_db.calculate_sha256", return_value="abc123"),
                patch("src.loaders.load_raw_to_db.extract_metadata", return_value={
                    "fuente": "test", "tipo_fuente": "test",
                    "ruta_relativa": "test.json", "nombre_archivo": "test.json",
                    "tamano_bytes": 2, "cantidad_registros": 0, "cantidad_columnas": 0,
                    "records": [],
                }),
                patch("src.loaders.load_raw_to_db.log_error"),
            ):
                run_loader(run_id="test-run-42")

        file_insert_queries = [q for q in captured_queries if "RETURNING" in q["sql"]]
        self.assertEqual(len(file_insert_queries), 1)
        self.assertIn("run_id", file_insert_queries[0]["sql"])
        self.assertEqual(file_insert_queries[0]["params"]["run_id"], "test-run-42")


if __name__ == "__main__":
    unittest.main()
