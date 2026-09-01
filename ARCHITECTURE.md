# Observatorio de Adopción de Agentes de IA - Arquitectura

Esta figura detalla el flujo de datos del observatorio, desde la extracción paralela hasta su visualización en el dashboard.

```mermaid
graph TD
    %% Estilos Globales
    classDef default fill:#1e1e1e,stroke:#333,stroke-width:2px,color:#fff,rx:5px,ry:5px;
    classDef source fill:#003366,stroke:#0055aa,stroke-width:2px,color:#fff;
    classDef etl fill:#336600,stroke:#55aa00,stroke-width:2px,color:#fff;
    classDef storage fill:#660033,stroke:#aa0055,stroke-width:2px,color:#fff;
    classDef api fill:#4b0082,stroke:#8a2be2,stroke-width:2px,color:#fff;
    classDef web fill:#b8860b,stroke:#daa520,stroke-width:2px,color:#fff;

    %% 1. Fuentes (Sources)
    subgraph Fuentes ["1. Orígenes de Datos (Sources)"]
        A1(GitHub API):::source
        A2(HackerNews):::source
        A3(Dev.to):::source
        A4(Reddit):::source
        A5(StackOverflow):::source
        A6(ArXiv):::source
        A7(Google Trends):::source
        A8(Catálogo y Formularios):::source
    end

    %% 2. Proceso ETL
    subgraph ETL ["2. Proceso ETL (Python)"]
        B1(Extracción Multifuente <br/> Paginación y Rate-Limits):::etl
        B2(Limpieza y <br/> Homologación Raw):::etl
        B3(Enriquecimiento Semántico <br/> y Deduplicación):::etl
        B4(Controles de Calidad <br/> Governance):::etl
    end

    %% 3. Almacenamiento DW
    subgraph DW ["3. Data Warehouse (PostgreSQL)"]
        C1[(Raw Schema <br/> JSON dumps)]:::storage
        C2[(Staging Schema <br/> Modelado normalizado)]:::storage
        C3[(Gold Schema <br/> Dimensiones y Hechos)]:::storage
        C4[(Audit Schema <br/> Calidad y Muestras)]:::storage
    end

    %% 4. Backend
    subgraph Backend ["4. Backend (FastAPI)"]
        D1(Endpoints KPI <br/> /api/kpi/):::api
        D2(Endpoints Gobierno <br/> /api/kpi/governance/):::api
    end

    %% 5. Frontend
    subgraph Frontend ["5. Visualización (Vue.js + Chart.js)"]
        E1[Dashboard Principal <br/> KPIs Globales]:::web
        E2[Panel de Gobierno <br/> Métricas de Calidad]:::web
    end

    %% Flujos de datos
    A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 -->|HTTP Requests| B1
    
    B1 -->|Carga Cruda| C1
    C1 -->|Lectura Cruda| B2
    B2 -->|Normalización| C2
    C2 -->|Enriquecimiento| B3
    B3 -->|Carga de Hechos| C3
    B3 -->|Generación Evidencia| B4
    B4 -->|Auditoría y Traza| C4
    
    C3 -->|Consultas Analíticas| D1
    C4 -->|Consultas de Calidad| D2
    
    D1 -->|JSON| E1
    D2 -->|JSON| E2
```

## Flujo del Pipeline
1. **Extracción (Raw):** El ETL conecta simultáneamente con múltiples APIs. Los resultados se guardan en crudo para asegurar trazabilidad.
2. **Transformación (Staging):** Los datos crudos se unifican bajo un esquema común, se mapean las entidades (agentes) y se detectan nulos.
3. **Carga Analítica (Gold):** Creación del modelo en estrella (star-schema) para potenciar la rapidez de lectura en el dashboard.
4. **Gobierno (Audit):** A lo largo del pipeline se generan métricas de reconciliación y calidad que se envían directamente a `audit`.
