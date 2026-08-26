# Observatorio de Adopción de Agentes de IA en Desarrollo de Software

[![Producción](https://img.shields.io/badge/Producción-biai.labtorres.me-blue)](https://biai.labtorres.me/)
![Arquitectura](https://img.shields.io/badge/Arquitectura-Medallion-green)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20React%20%7C%20PostgreSQL-lightgrey)

Plataforma de **Inteligencia de Negocios** que mide, consolida y visualiza el nivel de adopción de agentes de IA en el ecosistema de desarrollo de software. Integra 10 fuentes de datos heterogéneas mediante una pipeline ETL con arquitectura **Medallion** (Bronze → Silver → Gold) y expone un dashboard interactivo con KPIs de analítica y calidad.

---

## Visión General

| Capa | Tecnología | Descripción |
|------|-----------|-------------|
| **Extracción** | Python (APIs, scrapers, RSS) | 10 fuentes: GitHub, HackerNews, Dev.to, Reddit, Google Trends, AIDev Dataset, Google Forms, StackOverflow, arXiv, Google News |
| **Bronze (Raw)** | PostgreSQL | Archivos JSON crudos en `raw.raw_files` / `raw.raw_records` — evidencia inmutable de cada carga |
| **Silver (Staging)** | PostgreSQL | Tabla `stg_actividad_agente_ia` — deduplicación estricta, reconstruible desde Raw |
| **Quality (E3)** | Python + PostgreSQL | Framework de validación: completitud, duplicados, nulos críticos, formato. KPIs en esquema `audit` |
| **Gold (DWH)** | PostgreSQL | Dimensiones, tabla de hechos y vistas KPI pre-calculadas en esquema `gold` |
| **API** | FastAPI | Expone datos de `gold` y métricas de `audit` |
| **Dashboard** | React + Vite | SPA que grafica KPIs analíticos (E4) y calidad ETL (E3) |

---

## Métricas del Pipeline

_Ultima corrida verificada (Run ID: 27) con deduplicación estricta por origen._

| Métrica | Valor |
|---------|-------|
| Raw / Bronze acumulado | **399,900** registros |
| Staging / Silver consolidado | **127,364** registros |
| Gold — hechos finales | **127,364** (sin merma contra Staging) |
| Completitud Raw → Staging | 31.85% |
| Merma por deduplicación histórica | 68.15% |
| Duplicados reales descartados | 264,211 registros |
| Nulos críticos | **0** registros |
| Fuente propia (Google Forms) | 12 respuestas reales |

**Clave de deduplicación:**

```
fuente + plataforma + id_origen_registro + nombre_agente + fecha_evento
```

---

## Contrato Staging

| Concepto | Cantidad |
|----------|----------|
| Columnas físicas en PostgreSQL | 23 |
| Columnas analíticas exportadas (`staging_stats.csv`) | 21 |
| Columnas técnicas en BD (`id`, `fecha_carga`) | 2 |

Evidencia del contrato:
- `etl/docs/evidencias/staging_contract_columns.csv`
- `etl/docs/evidencias/staging_stats.csv`

---

## Fuentes de Datos

| Fuente | Método | Notas |
|--------|--------|-------|
| **GitHub** | REST API | Genera Raw y evidencia HTTP |
| **HackerNews** | Scraping (BeautifulSoup) | Genera Raw y evidencia HTTP |
| **Dev.to** | API pública | Filtro: `agent term OR (AI term AND software-development term)` |
| **Reddit** | Scraping (Playwright) | Búsquedas múltiples relevantes |
| **Google Trends** | pytrends | Rate limit 429 registrado como fallo documentado |
| **AIDev Dataset** | Parquet → JSON | Descarga automática desde Zenodo (Record 16919272) |
| **Fuente propia** | Google Forms → JSON | `etl/data/encuesta/encuesta.json` — integrada como adopción académica |
| **StackOverflow** | StackExchange API | Búsqueda por agente |
| **arXiv** | arXiv API | Rate limits respetados (3s entre consultas) |
| **Google News** | RSS | Búsqueda por agente |

---

## Evidencias de Auditoría

| Archivo | Descripción |
|---------|-------------|
| `source_execution_evidence.csv` | Estado de ejecución por fuente, cantidad extraída, HTTP status |
| `inventario_raw.csv` | Archivos nuevos cargados en la última ejecución |
| `inventario_raw_completo.csv` | Universo completo de Raw en PostgreSQL |
| `staging_stats.csv` | Dataset Staging reconstruido |
| `quality_summary.csv` | Resumen global Raw/Staging |
| `quality_issue_breakdown.csv` | Métricas por tipo de incidencia |
| `aidedev_agent_summary.csv` | Resumen analítico del AIDev Dataset por agente |
| `dedup_report.csv` | Duplicados reales por fuente |
| `nulls_matrix.csv` | Nulos por fuente y columna crítica |
| `casting_report.csv` | Errores de conversión por fuente/campo |
| `homologation_map.csv` | Reglas de homologación |
| `staging_contract_columns.csv` | Contrato físico y analítico de Staging |

---

## Inicio Rápido

El proyecto está completamente contenerizado. Para levantar el entorno local:

```bash
docker compose up -d --build
```

Esto despliega:

| Servicio | Contenedor | Puerto |
|----------|-----------|--------|
| PostgreSQL | `observatorio_db` | 5432 |
| Backend API | `observatorio_api` | 8000 |
| Frontend | `observatorio_frontend` | 8080 |
| ETL Worker | `observatorio_etl` | — |

Accedé al dashboard en: **[http://localhost:8080](http://localhost:8080)**

Desde la pestaña **Control de Extracción (ETL)** podés ejecutar el pipeline completo con un clic.

### Ejecución manual del pipeline

```bash
docker exec observatorio_etl python -m src.scripts.run_pipeline
```

### Ejecución por fase individual

```bash
cd etl && python -m src.extractors.github
cd etl && python -m src.extractors.hackernews
cd etl && python -m src.extractors.devto
cd etl && python -m src.extractors.reddit
cd etl && python -m src.extractors.google_trends
cd etl && python -m src.extractors.aidedev
cd etl && python -m src.extractors.fuente_propia
cd etl && python -m src.extractors.stackoverflow
cd etl && python -m src.extractors.arxiv
cd etl && python -m src.extractors.gnews
cd etl && python -m src.loaders.load_raw_to_db
cd etl && python -m src.staging.stg_build_unified
cd etl && python -m src.quality.quality_metrics
```

> **Nota — AIDev Dataset:** Si los archivos Parquet no se encuentran en `etl/data/manual/aidedev_ai_coding/`, el extractor se conecta automáticamente a la API de Zenodo, los descarga y los ubica en la carpeta correspondiente. No se requiere intervención manual.

---

## Limitaciones Conocidas

| Limitación | Impacto | Mitigación |
|-----------|---------|------------|
| Fuentes web: cambios HTML, anti-scraping, rate limits | Extractores pueden fallar parcialmente | Pipeline registra fallos sin detener la corrida |
| Google Trends: HTTP 429 | Extracción no disponible | Registrado como fallo documentado en evidencia |
| Dev.to: HTML variable | Artículos pueden no ser parseables | Fallback a API documentado en metadata Raw |
| Raw/Bronze: historico de cargas | Duplicados acumulados | Depurados en Silver/Staging sin alterar evidencia original |

---

## Stack Tecnológico

```
Python 3.x        FastAPI         PostgreSQL
React + Vite       Docker          BeautifulSoup
Playwright         pytrends        StackExchange API
arXiv API          Google News RSS Zenodo API
```

---

_Proyecto de Investigación — Observatorio sobre Adopción de Agentes de IA en Desarrollo de Software_
