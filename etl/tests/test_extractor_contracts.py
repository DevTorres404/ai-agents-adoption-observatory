import inspect
import unittest

from src.extractors.aidedev import extract_aidedev_catalog
from src.extractors.arxiv import extract_arxiv
from src.extractors.devto import extract_devto
from src.extractors.file_catalog import extract_and_validate_catalog
from src.extractors.fuente_propia import extract_google_forms_survey
from src.extractors.github import extract_github_repos
from src.extractors.gnews import extract_gnews
from src.extractors.google_trends import extract_trends
from src.extractors.hackernews import extract_hackernews
from src.extractors.reddit import extract_reddit
from src.extractors.stackoverflow import extract_stackoverflow


class ExtractorContractTest(unittest.TestCase):
    def test_all_extractors_accept_progressive_run_id(self):
        extractors = [
            extract_aidedev_catalog,
            extract_arxiv,
            extract_devto,
            extract_and_validate_catalog,
            extract_google_forms_survey,
            extract_github_repos,
            extract_gnews,
            extract_trends,
            extract_hackernews,
            extract_reddit,
            extract_stackoverflow,
        ]

        for extractor in extractors:
            with self.subTest(extractor=extractor.__name__):
                self.assertIn("run_id", inspect.signature(extractor).parameters)


if __name__ == "__main__":
    unittest.main()
