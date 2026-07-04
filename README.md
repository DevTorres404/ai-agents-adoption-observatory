# Observatorio IA - Arquitectura Medallion BI

Proyecto de Inteligencia de Negocios: **Observatorio sobre el Nivel de Adopcion de Agentes de IA en el Desarrollo de Software**.

El proyecto implementa una arquitectura **Medallion** completa para integrar fuentes heterogeneas, conservar evidencia cruda, consolidar datos analiticos y poblar un Data Warehouse dimensional en PostgreSQL.

## Arquitectura

El flujo sigue una arquitectura Medallion:

1. **Extraction**: GitHub REST API, HackerNews, Dev.to, Reddit, Google Trends, AIDev Dataset: AI Coding y encuesta Google Forms como fuente propia.
2. **Raw/Bronze**: archivos JSON en `data/raw/` y carga en PostgreSQL bajo `raw.raw_files` y `raw.raw_records`.
3. **Staging/Silver**: tabla `staging.stg_actividad_agente_ia`, reconstruible desde Raw.
4. **Quality**: metricas de completitud, duplicados reales, nulos criticos, casting, fuentes no mapeadas e inventario Raw completo.
5. **Gold/Data Warehouse**: esquema `gold` con dimensiones, tabla de hechos y vistas KPI.
6. **Evidence**: CSV academicos en `docs/evidencias/` y respaldo `dump_gold_entregable4.sql`.

## Ejecucion

```bash
docker-compose up -d
python -m src.scripts.run_pipeline --date 2026-06-27
```

Comandos por fase:

```bash
python -m src.extractors.github_api
python -m src.extractors.hackernews_scraper
python -m src.extractors.devto_scraper
python -m src.extractors.reddit_scraper
python -m src.extractors.trends_scraper
python -m src.extractors.aidedev_catalog
python -m src.extractors.google_forms_survey
python -m src.loaders.load_raw_to_db
python -m src.staging.stg_build_unified
python -m src.quality.quality_metrics
```

## Dataset AIDev (Descarga Automatizada)

El catalogo estructurado principal del entregable usa **AIDev Dataset: AI Coding**. Los archivos originales de este dataset (que superan los 300MB) son excluidos del control de versiones de Git por buenas prácticas de ingeniería de datos.

El extractor está diseñado para ser 100% autónomo. Al ejecutarse, verifica la existencia de los archivos requeridos (`all_pull_request.parquet`, `all_repository.parquet`, `all_user.parquet` y `data_table.md`) en la ruta local:

```text
data/manual/aidedev_ai_coding/
```

**Si los archivos no se encuentran, el extractor se conecta automáticamente a la API de Zenodo (Record 16919272), los descarga en su totalidad y los ubica en la carpeta correspondiente** antes de comenzar a procesarlos. No se requiere intervención manual para preparar el dataset.

El extractor que depende de estos archivos es:

```bash
python -m src.extractors.aidedev_catalog
```

Este extractor transforma los Parquet originales en Raw JSON dentro de:

```text
data/raw/archivos/catalogo/
```

## Contrato Staging

El contrato real queda definido asi:

- **23 columnas fisicas en PostgreSQL**.
- **21 columnas analiticas exportadas en `staging_stats.csv`**.
- **2 columnas tecnicas en BD**: `id` y `fecha_carga`.

La evidencia exacta del contrato se genera en:

- `docs/evidencias/staging_contract_columns.csv`
- `docs/evidencias/staging_stats.csv`

## Metricas verificadas

Ultima corrida verificada tras integrar `data/encuesta/encuesta.json` como fuente propia:

- Raw/Bronze acumulado en PostgreSQL: **358440 registros**.
- Staging/Silver consolidado: **120846 registros**.
- Completitud Raw acumulado vs Staging: **33.71%**.
- Merma controlada por deduplicacion historica: **66.29%**.
- Duplicados reales por clave compuesta: **237538 registros**.
- Nulos criticos: **0 registros**.
- Fuente propia Google Forms: **12 respuestas reales**.
- Gold Fact: **120846 hechos**, sin merma contra Staging.

La clave de deduplicacion es:

```text
fuente + plataforma + id_origen_registro + nombre_agente + fecha_evento
```

## Evidencias generadas

Los archivos principales de auditoria son:

- `source_execution_evidence.csv`: estado de ejecucion por fuente, cantidad extraida, HTTP status y ruta Raw.
- `inventario_raw.csv`: archivos nuevos cargados en la ultima ejecucion del loader.
- `inventario_raw_completo.csv`: universo completo de Raw en PostgreSQL.
- `staging_stats.csv`: dataset Staging reconstruido.
- `quality_summary.csv`: resumen global Raw/Staging.
- `quality_issue_breakdown.csv`: metricas separadas por tipo de incidencia.
- `aidedev_agent_summary.csv`: resumen analitico del AIDev Dataset por agente homologado.
- `dedup_report.csv`: duplicados reales por fuente.
- `nulls_matrix.csv`: nulos por fuente y columna critica.
- `casting_report.csv`: errores de conversion por fuente/campo.
- `homologation_map.csv`: reglas de homologacion.
- `staging_contract_columns.csv`: contrato fisico y analitico de Staging.

## Estado de fuentes

- **GitHub**: extractor REST API funcional; genera Raw y evidencia HTTP.
- **HackerNews**: scraper BeautifulSoup funcional; genera Raw y evidencia HTTP.
- **Dev.to**: extractor relevante con API publica y filtro `agent term OR (AI term AND software-development term)`; genera Raw y evidencia HTTP.
- **Reddit**: scraper Playwright funcional con busquedas multiples relevantes; genera Raw y evidencia HTTP.
- **Google Trends**: extractor pytrends funcional en la corrida final; si aparece rate limit 429, se registra como fallo y no se reporta como extraccion exitosa.
- **Catalogo / AIDev Dataset**: fuente estructurada en Parquet transformada a Raw JSON analitico; reemplaza el catalogo manual como dataset principal.
- **Fuente propia / Google Forms**: `data/encuesta/encuesta.json` se normaliza como Raw en `data/raw/fuente_propia/fuente_propia/` y se integra a Staging/Gold como adopcion academica.

## Limitaciones conocidas

- Las fuentes web pueden variar por cambios HTML, bloqueo anti-scraping o rate limits.
- Google Trends puede devolver 429; el pipeline lo registra como fallo documentado.
- Dev.to puede no exponer articulos parseables en HTML; el fallback API queda documentado en metadata Raw y en `source_execution_evidence.csv`.
- Raw/Bronze conserva historico de cargas; por eso los duplicados acumulados se depuran en Silver/Staging sin alterar la evidencia original.
