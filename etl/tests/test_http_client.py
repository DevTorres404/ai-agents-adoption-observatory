import unittest

import requests

from src.utils.http_client import AntiScrapingError, HttpClient, RateLimitError


class _Response:
    def __init__(self, status_code, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload or {}
        self.text = ""
        self.url = "https://example.test/resource"

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class _Session:
    def __init__(self, responses):
        self.headers = {}
        self.responses = iter(responses)

    def get(self, *args, **kwargs):
        return next(self.responses)


class HttpClientRateLimitTest(unittest.TestCase):
    def test_waits_until_rate_limit_reset_then_retries(self):
        sleeps = []
        client = HttpClient(
            default_delay=0,
            clock=lambda: 100,
            sleeper=sleeps.append,
            max_rate_limit_wait=10,
            max_rate_limit_retries=1,
        )
        client.session = _Session([
            _Response(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "105"}),
            _Response(200),
        ])

        response = client.get("https://example.test/resource")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sleeps, [5])

    def test_retry_after_wait_is_bounded(self):
        sleeps = []
        client = HttpClient(
            default_delay=0,
            sleeper=sleeps.append,
            max_rate_limit_wait=7,
            max_rate_limit_retries=1,
        )
        client.session = _Session([
            _Response(429, {"Retry-After": "30"}),
            _Response(200),
        ])

        client.get("https://example.test/resource")

        self.assertEqual(sleeps, [7])

    def test_plain_403_is_anti_scraping_not_rate_limit(self):
        client = HttpClient(default_delay=0, sleeper=lambda _: None)
        client.session = _Session([_Response(403)])

        with self.assertRaises(AntiScrapingError):
            client.get("https://example.test/resource")

    def test_exhausted_retry_raises_distinguishable_rate_limit(self):
        client = HttpClient(
            default_delay=0,
            sleeper=lambda _: None,
            max_rate_limit_retries=0,
        )
        client.session = _Session([_Response(429, {"Retry-After": "12"})])

        with self.assertRaises(RateLimitError) as caught:
            client.get("https://example.test/resource")

        self.assertEqual(caught.exception.retry_after, 12)


if __name__ == "__main__":
    unittest.main()
