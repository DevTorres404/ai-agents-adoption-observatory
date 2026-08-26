import unittest

from src.scripts.run_pipeline import derive_pipeline_status
from src.utils.extraction_evidence import ExtractionResult, ExtractionStatus


class PipelineStatusTest(unittest.TestCase):
    def test_source_failure_with_useful_data_marks_pipeline_partial(self):
        results = [
            ExtractionResult("github", ExtractionStatus.PARTIAL_SUCCESS, 100),
            ExtractionResult("gnews", ExtractionStatus.SUCCESS, 20),
        ]

        self.assertEqual(derive_pipeline_status(results), "partial_success")

    def test_critical_phase_failure_overrides_source_results(self):
        results = [ExtractionResult("github", ExtractionStatus.SUCCESS, 100)]

        self.assertEqual(
            derive_pipeline_status(results, critical_failure=True),
            "failed",
        )


if __name__ == "__main__":
    unittest.main()
