import requests
import time
from email.utils import parsedate_to_datetime

from src.utils.logger import global_logger


class RateLimitError(requests.exceptions.HTTPError):
    def __init__(self, message, response=None, retry_after=None, reset_at=None):
        super().__init__(message, response=response)
        self.retry_after = retry_after
        self.reset_at = reset_at


class AntiScrapingError(requests.exceptions.HTTPError):
    pass


class HttpClient:
    """
    Cliente HTTP unificado que maneja Delays, User-Agent y excepciones comunes (403, 404, etc).
    """
    def __init__(
        self,
        source_name="http",
        default_delay=2,
        timeout=10,
        clock=None,
        sleeper=None,
        max_rate_limit_wait=60,
        max_rate_limit_retries=1,
    ):
        self.source_name = source_name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BI-Project-UPSE"
        })
        self.default_delay = default_delay
        self.timeout = timeout
        self.last_status_code = None
        self.clock = clock or time.time
        self.sleeper = sleeper or time.sleep
        self.max_rate_limit_wait = max(0, max_rate_limit_wait)
        self.max_rate_limit_retries = max(0, max_rate_limit_retries)

    def _rate_limit_delay(self, response, attempt):
        retry_after = response.headers.get("Retry-After")
        reset_at = response.headers.get("X-RateLimit-Reset")
        raw_delay = None

        if retry_after:
            try:
                raw_delay = max(0.0, float(retry_after))
            except ValueError:
                try:
                    raw_delay = max(
                        0.0,
                        parsedate_to_datetime(retry_after).timestamp() - self.clock(),
                    )
                except (TypeError, ValueError, OverflowError):
                    raw_delay = None
        elif reset_at:
            try:
                raw_delay = max(0.0, float(reset_at) - self.clock())
            except ValueError:
                raw_delay = None

        if raw_delay is None:
            raw_delay = max(1.0, self.default_delay * (2 ** attempt))
        return raw_delay, min(raw_delay, self.max_rate_limit_wait)

    @staticmethod
    def _is_rate_limited(response):
        if response.status_code == 429:
            return True
        if response.status_code != 403:
            return False
        remaining = response.headers.get("X-RateLimit-Remaining")
        body = str(getattr(response, "text", "")).lower()
        return (
            remaining == "0"
            or "Retry-After" in response.headers
            or "X-RateLimit-Reset" in response.headers
            or "rate limit" in body
        )

    def get(self, url, params=None, headers=None, is_json=None):
        """
        Ejecuta GET y devuelve Response por defecto.
        Si is_json=False, devuelve response.text para scrapers HTML.
        Si is_json=True, devuelve response.json().
        """
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        for attempt in range(self.max_rate_limit_retries + 1):
            if self.default_delay > 0:
                self.sleeper(self.default_delay)
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                self.last_status_code = response.status_code
                response.raise_for_status()
                global_logger.info(f"{self.source_name}: HTTP {response.status_code} GET {response.url}")
                if is_json is True:
                    return response.json()
                if is_json is False:
                    return response.text
                return response
            except requests.exceptions.HTTPError as exc:
                response = exc.response
                status_code = response.status_code
                self.last_status_code = status_code
                if self._is_rate_limited(response):
                    retry_after, bounded_wait = self._rate_limit_delay(response, attempt)
                    reset_at = response.headers.get("X-RateLimit-Reset")
                    if attempt < self.max_rate_limit_retries:
                        global_logger.warning(
                            f"Rate limit en {url}; reintento en {bounded_wait:g}s "
                            f"(espera solicitada {retry_after:g}s)."
                        )
                        if bounded_wait > 0:
                            self.sleeper(bounded_wait)
                        continue
                    raise RateLimitError(
                        f"Rate limit agotado en {url}",
                        response=response,
                        retry_after=retry_after,
                        reset_at=float(reset_at) if reset_at else None,
                    ) from exc
                if status_code == 403:
                    global_logger.error(f"Error 403 Forbidden anti-scraping en {url}.")
                    raise AntiScrapingError(
                        f"Acceso bloqueado por anti-scraping en {url}",
                        response=response,
                    ) from exc
                if status_code == 404:
                    global_logger.warning(f"Error 404 Not Found en {url}.")
                elif status_code >= 500:
                    global_logger.error(f"Error del servidor {status_code} en {url}.")
                else:
                    global_logger.error(f"Error HTTP {status_code} en {url}: {exc}")
                raise
            except requests.exceptions.Timeout:
                global_logger.error(f"Timeout al conectar con {url}")
                raise
            except requests.exceptions.RequestException as exc:
                global_logger.error(f"Error de conexión con {url}: {exc}")
                raise
