import requests
import time
from src.utils.logger import global_logger

class HttpClient:
    """
    Cliente HTTP unificado que maneja Delays, User-Agent y excepciones comunes (403, 404, etc).
    """
    def __init__(self, source_name="http", default_delay=2, timeout=10):
        self.source_name = source_name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 BI-Project-UPSE"
        })
        self.default_delay = default_delay
        self.timeout = timeout
        self.last_status_code = None

    def get(self, url, params=None, headers=None, is_json=None):
        """
        Ejecuta GET y devuelve Response por defecto.
        Si is_json=False, devuelve response.text para scrapers HTML.
        Si is_json=True, devuelve response.json().
        """
        time.sleep(self.default_delay)
        
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            response = self.session.get(url, params=params, headers=request_headers, timeout=self.timeout)
            self.last_status_code = response.status_code
            response.raise_for_status()
            global_logger.info(f"{self.source_name}: HTTP {response.status_code} GET {response.url}")
            if is_json is True:
                return response.json()
            if is_json is False:
                return response.text
            return response
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            self.last_status_code = status_code
            if status_code == 403:
                global_logger.error(f"Error 403 Forbidden en {url}. Probablemente bloqueado por anti-scraping.")
            elif status_code == 404:
                global_logger.warning(f"Error 404 Not Found en {url}.")
            elif status_code == 429:
                global_logger.error(f"Error 429 Too Many Requests en {url}. Se necesita mayor delay.")
            elif status_code >= 500:
                global_logger.error(f"Error del servidor {status_code} en {url}.")
            else:
                global_logger.error(f"Error HTTP {status_code} en {url}: {e}")
            raise
        except requests.exceptions.Timeout:
            global_logger.error(f"Timeout al conectar con {url}")
            raise
        except requests.exceptions.RequestException as e:
            global_logger.error(f"Error de conexión con {url}: {e}")
            raise
