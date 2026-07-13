# Contexto Actual del Proyecto

**Nombre del Proyecto:** Observatorio sobre el Nivel de Adopción de Agentes de IA en el Desarrollo de Software
**Asignatura:** Inteligencia de Negocios (BI)

---

## 1. Objetivo del Proyecto
El proyecto busca medir, analizar y visualizar el nivel de adopción e impacto de los agentes de Inteligencia Artificial (IA) en el ciclo de vida del desarrollo de software, consolidando información de múltiples fuentes para la toma de decisiones.

## 2. Estado General (Hasta el Entregable 3)
El proyecto ha completado exitosamente la fase de ingeniería de datos y preparación. Actualmente, cuenta con un pipeline **ETL** (Extracción, Transformación y Carga) robusto y un marco de **Calidad de Datos** auditable. Toda la arquitectura se basa en el modelo **Medallion** (Bronze / Silver / Gold), habiendo alcanzado la capa Silver (Staging).

### Arquitectura Implementada:
1. **Extracción (Data Sources):** Se recopilan datos desde fuentes heterogéneas mediante scripts en Python (APIs y Web Scraping):
   * GitHub REST API
   * HackerNews
   * Dev.to
   * Reddit
   * Google Trends
   * *Dataset AIDev (AI Coding)*: Descarga automatizada desde Zenodo como catálogo estructurado principal.
2. **Capa Raw (Bronze):** Los datos se almacenan temporalmente como archivos JSON y luego se cargan en PostgreSQL bajo el esquema `raw`.
3. **Capa Staging (Silver):** Los datos se unifican, limpian y homologan en la tabla `staging.stg_actividad_agente_ia`, la cual cuenta con 23 columnas físicas preparadas para el análisis.
4. **Capa de Calidad (Quality Framework):** Se ejecutan validaciones estrictas generando métricas sobre completitud (actualmente 99.78%), duplicados, valores nulos y errores de tipado, emitiendo reportes CSV de evidencia.

## 3. Infraestructura y Tecnologías
* **Motor de Base de Datos:** PostgreSQL 16 (desplegado mediante Docker Compose bajo el contenedor `observatorio_db`).
* **Orquestación y Lógica:** Python 3 (uso de librerías como `requests`, `beautifulsoup4`, `playwright`, `pandas`, `pytrends`).
* **Almacenamiento de Evidencias:** Archivos `.csv` ubicados en `etl/docs/evidencias/` que certifican el contrato de datos.

## 4. Métricas de Datos Actuales (Última Corrida)
* **Registros Extraídos (Raw):** ~120,026 registros.
* **Registros Consolidados (Staging):** ~119,760 registros útiles.
* **Nulos Críticos:** 0
* **Merma de Datos:** Apenas 0.22% en la transición de Raw a Staging.

## 5. Próximos Pasos (Entregable 4 - Gold / Data Warehouse)
El proyecto se encuentra listo para iniciar el modelado de la **Capa Gold (Data Warehouse y Analítica)**. Esto implicará:
1. Construir las tablas de Hechos y Dimensiones (modelo estrella/copo de nieve).
2. Poblar el Data Warehouse a partir de la tabla maestra de Staging.
3. Generar consultas analíticas complejas (SQL) y materializar los KPIs de negocio.
