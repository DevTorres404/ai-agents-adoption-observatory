import inspect
import unittest

from src.extractors.aidedev import extract_aidedev_catalog
from src.extractors.file_catalog import extract_and_validate_catalog
from src.extractors.github import extract_github_repos
from src.extractors.google_trends import extract_trends
from src.extractors.hackernews import extract_hackernews


class ExtractorContractTest(unittest.TestCase):
    def test_all_extractors_accept_progressive_run_id(self):
        extractors = [
            extract_aidedev_catalog,
            extract_and_validate_catalog,
            extract_github_repos,
            extract_trends,
            extract_hackernews,
        ]

        for extractor in extractors:
            with self.subTest(extractor=extractor.__name__):
                self.assertIn("run_id", inspect.signature(extractor).parameters)


if __name__ == "__main__":
    unittest.main()
