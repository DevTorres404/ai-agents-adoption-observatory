import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.extractors import devto, github, gnews
from src.utils.extraction_evidence import (
    EvidenceRun,
    ExtractionStatus,
    evidence_context,
)


class _Response:
    def __init__(self, items, status_code=200, total_count=None):
        self._items = items
        self.status_code = status_code
        self.headers = {"X-RateLimit-Remaining": "10"}
        self.total_count = len(items) if total_count is None else total_count

    def json(self):
        return {"items": self._items, "total_count": self.total_count}


class GithubOutcomeTest(unittest.TestCase):
    def test_large_result_set_is_partitioned_and_deduplicated(self):
        class PartitionClient:
            last_status_code = 200
            requested = []

            def __init__(self, *args, **kwargs):
                type(self).requested = []

            def get(self, *args, **kwargs):
                params = kwargs["params"]
                type(self).requested.append(params.copy())
                date_range = params["q"].split("created:", 1)[1]
                if date_range == f"{github.SOURCE_START_DATE}..{github.SOURCE_END_DATE}":
                    return _Response([{"id": "probe"}], total_count=1501)
                if len([item for item in type(self).requested if "created:" in item["q"]]) == 2:
                    return _Response([{"id": 1}], total_count=1)
                return _Response([{"id": 1}, {"id": 2}], total_count=2)

        with tempfile.TemporaryDirectory() as directory:
            run = EvidenceRun("79", Path(directory) / "evidence", Path(directory) / "legacy.csv")
            with (
                patch.object(github, "HttpClient", PartitionClient),
                patch.object(github, "RAW_DIR", Path(directory) / "raw"),
                patch.object(github, "log_error"),
                evidence_context(run),
            ):
                result = github.extract_github_repos(
                    queries=["Cursor"], pages=15, per_page=100, run_id="79"
                )
                payload = json.loads(Path(result.raw_path).read_text(encoding="utf-8"))

        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertEqual(result.records_extracted, 2)
        self.assertNotIn("probe", {item.get("id") for item in payload["items"]})
        self.assertTrue(all(params["page"] <= 10 for params in PartitionClient.requested))
        date_ranges = [params["q"].split("created:", 1)[1] for params in PartitionClient.requested[1:]]
        self.assertEqual(len(date_ranges), 2)
        self.assertNotEqual(date_ranges[0].split("..")[1], date_ranges[1].split("..")[0])

    def test_query_failure_after_useful_data_yields_partial_success(self):
        class FakeClient:
            last_status_code = None

            def __init__(self, *args, **kwargs):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    self.last_status_code = 200
                    return _Response([{"id": 1}])
                self.last_status_code = 403
                raise RuntimeError("rate limit")

        with tempfile.TemporaryDirectory() as directory:
            run = EvidenceRun("77", Path(directory) / "evidence", Path(directory) / "legacy.csv")
            with (
                patch.object(github, "HttpClient", FakeClient),
                patch.object(github, "RAW_DIR", Path(directory) / "raw"),
                patch.object(github, "log_error"),
                evidence_context(run),
            ):
                result = github.extract_github_repos(
                    queries=["Cursor", "Codex"],
                    pages=1,
                    per_page=1,
                    run_id="77",
                )

        self.assertEqual(result.status, ExtractionStatus.PARTIAL_SUCCESS)
        query_results = [item for item in run.results if item.query]
        self.assertEqual(
            [(item.query.split("|", 1)[0], item.status) for item in query_results],
            [
                ("Cursor", ExtractionStatus.SUCCESS),
                ("Codex", ExtractionStatus.FAILED),
            ],
        )
        self.assertEqual(run.results[-1].status, ExtractionStatus.PARTIAL_SUCCESS)


class DevToOutcomeTest(unittest.TestCase):
    def test_api_failure_preserves_html_records_as_partial_success(self):
        class FakeClient:
            last_status_code = 503

            def __init__(self, *args, **kwargs):
                pass

        html_record = {
            "id": "https://dev.to/article",
            "title": "Codex article",
            "url": "https://dev.to/article",
            "created_at": "2025-01-01",
        }
        with tempfile.TemporaryDirectory() as directory:
            run = EvidenceRun("80", Path(directory) / "evidence", Path(directory) / "legacy.csv")
            with (
                patch.object(devto, "HttpClient", FakeClient),
                patch.object(devto, "RAW_DIR", Path(directory) / "raw"),
                patch.object(devto, "extract_from_html", return_value=[html_record]),
                patch.object(devto, "extract_from_public_api", side_effect=RuntimeError("api down")),
                patch.object(devto, "log_error"),
                evidence_context(run),
            ):
                result = devto.extract_devto(run_id="80")

        self.assertEqual(result.status, ExtractionStatus.PARTIAL_SUCCESS)
        self.assertEqual(result.records_extracted, 1)
        self.assertIn("80", Path(result.raw_path).name)


class GNewsOutcomeTest(unittest.TestCase):
    def test_query_failure_is_not_overwritten_by_final_success(self):
        rss = """<rss><channel><item><title>News</title><link>https://n.test/1</link>
        <pubDate>Thu, 26 Oct 2023 07:00:00 GMT</pubDate><source>Publisher</source>
        </item></channel></rss>"""

        class FakeClient:
            last_status_code = 200

            def __init__(self, *args, **kwargs):
                self.calls = 0

            def get(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return rss
                self.last_status_code = 503
                raise RuntimeError("unavailable")

        with tempfile.TemporaryDirectory() as directory:
            run = EvidenceRun("78", Path(directory) / "evidence", Path(directory) / "legacy.csv")
            with (
                patch.object(gnews, "HttpClient", FakeClient),
                patch.object(gnews, "RAW_DIR", Path(directory) / "raw"),
                patch.object(gnews, "AGENT_QUERIES", ["Cursor AI", "Codex"]),
                patch.object(gnews, "log_error"),
                evidence_context(run),
            ):
                result = gnews.extract_gnews(run_id="78", sleeper=lambda _: None)

        self.assertEqual(result.status, ExtractionStatus.PARTIAL_SUCCESS)
        self.assertEqual(run.results[-1].status, ExtractionStatus.PARTIAL_SUCCESS)
        self.assertEqual(run.results[-1].records_extracted, 1)


if __name__ == "__main__":
    unittest.main()
