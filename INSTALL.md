# Guía de Instalación y Reproducción

El **Observatorio de Adopción de Agentes de IA** está diseñado bajo una arquitectura de microservicios usando Docker Compose, lo que garantiza que pueda ser desplegado y reproducido en cualquier entorno con dependencias mínimas.

## Requisitos Previos

* **Docker** (versión 24.0 o superior)
* **Docker Compose** (versión 2.20 o superior)
* Al menos 4GB de RAM libre (recomendado para el proceso ETL completo).
* (Opcional pero recomendado) Tokens de API para las fuentes de extracción (GitHub, Reddit) para evitar bloqueos por límite de peticiones anónimas (rate-limits).

---

## 🚀 Despliegue Rápido (Quickstart)

El repositorio incluye un archivo de orquestación que levanta todos los componentes simultáneamente.

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/DevTorres404/ai-agents-adoption-observatory.git
   cd ai-agents-adoption-observatory
   ```

2. **Configurar variables de entorno (Opcional):**
   Puedes crear un archivo `.env` en la raíz del proyecto para definir configuraciones específicas (tokens de API, puertos). Si no lo creas, el sistema usará valores y puertos por defecto.
   ```env
   # .env
   GITHUB_TOKEN=tu_token_aqui
   REDDIT_CLIENT_ID=tu_client_id
   REDDIT_CLIENT_SECRET=tu_secret
   ```

3. **Levantar los servicios:**
   ```bash
   docker compose up -d --build
   ```

Este comando levantará los siguientes componentes:
* **postgres (observatorio_db):** Base de datos relacional (Puerto 5433 local). Inicializa automáticamente todos los esquemas (raw, staging, gold, audit).
* **backend (observatorio_api):** API REST en FastAPI que expone los datos del Data Warehouse (Puerto interno 8000).
* **frontend (observatorio_frontend):** Aplicación web en React + Vite (Accesible en `http://localhost:8080`).
* **etl_runner (etl):** Proceso batch bajo demanda para extraer y transformar la información. Al estar en un profile, se debe ejecutar manualmente con: `docker compose run --rm etl python -m src.scripts.run_pipeline`

---

## 📊 Arquitectura de Extracción de Datos (ETL)

El corazón de este observatorio es su pipeline de datos (ETL). ¿De dónde sale la información que ves en el Dashboard?

1. **GitHub (Adopción Técnica y Popularidad):** Extrae la cantidad de repositorios creados (estrellas, forks) que mencionan explícitamente el uso de agentes específicos (Cursor, Copilot, Claude Code, etc.). 
2. **StackOverflow (Resolución de Problemas):** Mide la cantidad de preguntas y volumen de discusión sobre errores o integraciones técnicas de cada agente.
3. **Reddit (Percepción y Comunidad):** Analiza subreddits de programación para identificar menciones orgánicas, adopción real y sentimiento de la comunidad frente a estas herramientas.
4. **Google Trends (Interés General):** Rastrea el volumen de búsquedas globales para entender cómo el hype y el interés de mercado sube o baja con el tiempo.
5. **arXiv (Investigación Científica):** Mide qué agentes están siendo citados o utilizados en publicaciones académicas sobre IA.
6. **Catálogos y Formulario Propio:** Datos estructurados provenientes de directorios de herramientas IA (como AIDev) y recolección de encuestas (Google Forms) de la propia comunidad.

### Ejecución y Reproducibilidad del ETL

El ETL está diseñado para ser **idempotente y reproducible**. 
Dado que analiza años de historial (ej. todo 2025 y 2026) desde múltiples fuentes masivas (paginando para sortear límites de API), **el proceso de extracción inicial (Cold Start) puede tardar varias horas.**

Para reiniciar completamente el observatorio y forzar una re-extracción de todos los datos históricos desde cero:

```bash
# 1. Bajar los servicios y eliminar el volumen de persistencia de PostgreSQL
docker compose down -v

# 2. Volver a levantar el entorno (esto dispara la creación de tablas y el ETL completo)
docker compose up -d --build

# 3. Monitorear el progreso de extracción (Fase 1)
docker logs -f ai-agents-adoption-observatory-etl-run-1
```

*(Nota: En la fase de Extracción, el ETL descarga cientos de páginas de la API de GitHub de a 100 resultados por vez. No interrumpas el proceso).*

---

## 🔍 Gobierno y Calidad de Datos

El Observatorio no solo muestra gráficos, sino que garantiza la **calidad (Governance)** de lo que estás viendo.

Durante la carga del Data Warehouse (Fase Gold), el sistema genera automáticamente:
* **Matriz de Nulos:** Vigila la completitud de los registros.
* **Cobertura Semántica:** Garantiza que los registros raw se hayan mapeado correctamente a sus dimensiones de negocio.
* **Métricas de Frescura (Freshness):** Registra hace cuánto tiempo se actualizó cada fuente.
* **Muestras de Relevancia:** Extrae ejemplos de los datos crudos para poder auditar si un repositorio clasificado como "Cursor" verdaderamente habla del IDE o es un falso positivo.

Todo esto es consultable desde el endpoint `/api/kpi/governance/metrics` y `/api/kpi/governance/sample`.
