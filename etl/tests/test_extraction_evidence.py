import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.extraction_evidence import (
    EvidenceRun,
    ExtractionResult,
    ExtractionStatus,
    aggregate_status,
    evidence_context,
    log_source_execution,
    raw_output_path,
)


class ExtractionStatusTest(unittest.TestCase):
    def test_aggregate_status_distinguishes_empty_failed_and_partial(self):
        success = ExtractionResult("github", ExtractionStatus.SUCCESS, records_extracted=2)
        empty = ExtractionResult("gnews", ExtractionStatus.EMPTY)
        failed = ExtractionResult("reddit", ExtractionStatus.FAILED)

        self.assertEqual(aggregate_status([]), ExtractionStatus.EMPTY)
        self.assertEqual(aggregate_status([empty]), ExtractionStatus.EMPTY)
        self.assertEqual(aggregate_status([failed]), ExtractionStatus.FAILED)
        self.assertEqual(aggregate_status([success, empty]), ExtractionStatus.SUCCESS)
        self.assertEqual(
            aggregate_status([success, failed]),
            ExtractionStatus.PARTIAL_SUCCESS,
        )

    def test_failed_unit_with_useful_records_is_partial(self):
        result = ExtractionResult(
            "github",
            ExtractionStatus.FAILED,
            records_extracted=100,
            query="Cursor",
        )

        self.assertEqual(aggregate_status([result]), ExtractionStatus.PARTIAL_SUCCESS)


class EvidencePublicationTest(unittest.TestCase):
    def test_raw_paths_are_unique_between_runs_on_the_same_timestamp(self):
        timestamp = __import__("datetime").datetime(2026, 8, 26, 12, 0, 0)
        with evidence_context(EvidenceRun("run-1")):
            first = raw_output_path("github", now=timestamp)
        with evidence_context(EvidenceRun("run-2")):
            second = raw_output_path("github", now=timestamp)

        self.assertNotEqual(first.name, second.name)
        self.assertIn("run-1", first.name)
        self.assertIn("run-2", second.name)

    def test_run_scoped_evidence_captures_run_id_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = EvidenceRun(
                run_id="run-42",
                evidence_root=root / "runs",
                legacy_file=root / "source_execution_evidence.csv",
            )

            with evidence_context(run):
                result = log_source_execution(
                    "github",
                    "success",
                    3,
                    200,
                    "https://api.github.test",
                    query="Cursor",
                )

            self.assertEqual(result.run_id, "run-42")
            self.assertEqual(result.query, "Cursor")
            self.assertFalse((root / "runs" / "run-42" / "evidence.csv").exists())

            publication = run.publish()

            with publication.evidence_file.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["run_id"], "run-42")
            self.assertEqual(rows[0]["query"], "Cursor")
            self.assertEqual(rows[0]["status"], "success")

            summary = json.loads(publication.summary_file.read_text(encoding="utf-8"))
            self.assertEqual(summary["run_id"], "run-42")
            self.assertEqual(summary["status"], "success")

    def test_publication_uses_temporary_files_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = EvidenceRun(
                run_id="atomic-run",
                evidence_root=root / "runs",
                legacy_file=root / "source_execution_evidence.csv",
            )
            run.record(ExtractionResult("github", ExtractionStatus.SUCCESS, 1))

            from src.utils import extraction_evidence

            real_replace = extraction_evidence.os.replace
            replacements = []

            def recording_replace(source, destination):
                replacements.append((Path(source), Path(destination)))
                return real_replace(source, destination)

            with patch.object(extraction_evidence.os, "replace", side_effect=recording_replace):
                publication = run.publish()

            self.assertTrue(publication.evidence_file.exists())
            self.assertTrue(publication.summary_file.exists())
            self.assertGreaterEqual(len(replacements), 3)
            self.assertTrue(all(source.suffix == ".tmp" for source, _ in replacements))
            self.assertFalse(any(root.rglob("*.tmp")))

    def test_failed_run_does_not_replace_last_valid_legacy_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "source_execution_evidence.csv"

            valid = EvidenceRun("valid", root / "runs", legacy)
            valid.record(ExtractionResult("github", ExtractionStatus.SUCCESS, 2))
            valid.publish()
            previous = legacy.read_text(encoding="utf-8")

            failed = EvidenceRun("failed", root / "runs", legacy)
            failed.record(ExtractionResult("gnews", ExtractionStatus.FAILED, 0))
            failed.publish()

            self.assertEqual(legacy.read_text(encoding="utf-8"), previous)
            self.assertTrue((root / "runs" / "failed" / "evidence.csv").exists())


if __name__ == "__main__":
    unittest.main()
