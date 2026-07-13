FROM python:3.12-slim

RUN groupadd -r fastapi && useradd -r -g fastapi -d /app -s /bin/false fastapi

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/__init__.py ./backend/
COPY backend/main.py ./backend/
COPY backend/database.py ./backend/
COPY backend/routes.py ./backend/

RUN chown -R fastapi:fastapi /app

USER fastapi

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "60", "--log-level", "info"]
