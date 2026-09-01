-- ==========================================================
-- ENTREGABLE 4 - MODELO DIMENSIONAL FISICO GOLD
-- Proyecto BI: Observatorio sobre adopcion de agentes de IA
-- Motor: PostgreSQL
--
-- Fuente unica permitida para carga posterior:
-- staging.stg_actividad_agente_ia
--
-- Este script solo crea estructura. No inserta datos, no usa mock data
-- y no consulta Raw.
--
-- Granularidad de la tabla de hechos:
-- Un registro representa una actividad observada de adopcion o mencion
-- de un agente de IA en una fuente, plataforma y fecha determinada.
-- ==========================================================

CREATE SCHEMA IF NOT EXISTS gold;

-- Eliminar primero la tabla de hechos para respetar dependencias FK.
DROP TABLE IF EXISTS gold.fact_actividad_agente_ia CASCADE;
DROP TABLE IF EXISTS gold.dim_comunidad CASCADE;
DROP TABLE IF EXISTS gold.dim_tecnologia CASCADE;
DROP TABLE IF EXISTS gold.dim_plataforma CASCADE;
DROP TABLE IF EXISTS gold.dim_fuente CASCADE;
DROP TABLE IF EXISTS gold.dim_agente CASCADE;
DROP TABLE IF EXISTS gold.dim_tiempo CASCADE;


-- ==========================================================
-- DIMENSION: TIEMPO
-- Una fila por fecha calendario observada en Staging.
-- ==========================================================
CREATE TABLE gold.dim_tiempo (
    id_tiempo BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    anio SMALLINT NOT NULL,
    semestre SMALLINT NOT NULL CHECK (semestre BETWEEN 1 AND 2),
    trimestre SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mes SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nombre_mes VARCHAR(20) NOT NULL,
    semana_anio SMALLINT NOT NULL CHECK (semana_anio BETWEEN 1 AND 53),
    dia_mes SMALLINT NOT NULL CHECK (dia_mes BETWEEN 1 AND 31),
    dia_semana SMALLINT NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    nombre_dia VARCHAR(20) NOT NULL,
    es_fin_semana BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_tiempo_fecha UNIQUE (fecha)
);


-- ==========================================================
-- DIMENSION: AGENTE
-- Describe el agente de IA homologado desde Staging.
-- ==========================================================
CREATE TABLE gold.dim_agente (
    id_agente BIGSERIAL PRIMARY KEY,
    nombre_agente VARCHAR(100) NOT NULL,
    categoria_agente VARCHAR(100),
    tipo_agente VARCHAR(100) NOT NULL DEFAULT 'No especificado',
    familia_modelo VARCHAR(100),
    proveedor VARCHAR(120),
    caracteristica_clave VARCHAR(255),
    modelo_precios VARCHAR(100),
    es_agente_identificado BOOLEAN NOT NULL DEFAULT TRUE,
    descripcion TEXT,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_agente_nombre UNIQUE (nombre_agente)
);


-- ==========================================================
-- DIMENSION: FUENTE
-- Describe el origen analitico de la observacion.
-- ==========================================================
CREATE TABLE gold.dim_fuente (
    id_fuente BIGSERIAL PRIMARY KEY,
    nombre_fuente VARCHAR(100) NOT NULL,
    tipo_fuente VARCHAR(50) NOT NULL,
    categoria_fuente VARCHAR(100),
    confiabilidad_fuente VARCHAR(100) NOT NULL DEFAULT 'No especificado',
    descripcion TEXT,
    es_fuente_propia BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_fuente UNIQUE (nombre_fuente, tipo_fuente)
);


-- ==========================================================
-- DIMENSION: PLATAFORMA
-- Permite analizar el canal o plataforma especifica de captura.
-- ==========================================================
CREATE TABLE gold.dim_plataforma (
    id_plataforma BIGSERIAL PRIMARY KEY,
    nombre_plataforma VARCHAR(100) NOT NULL,
    tipo_plataforma VARCHAR(100),
    ecosistema VARCHAR(100),
    descripcion TEXT,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_plataforma_nombre UNIQUE (nombre_plataforma)
);


-- ==========================================================
-- DIMENSION: TECNOLOGIA
-- Clasifica la tecnología, capacidad o área técnica observada.
-- Se alimenta con metadata estructurada y reglas contextuales trazables
-- generadas explícitamente en staging.stg_actividad_agente_ia.
-- ==========================================================
CREATE TABLE gold.dim_tecnologia (
    id_tecnologia BIGSERIAL PRIMARY KEY,
    nombre_tecnologia VARCHAR(120) NOT NULL,
    categoria_tecnologia VARCHAR(100) NOT NULL,
    dominio_tecnologico VARCHAR(120),
    tipo_senal VARCHAR(100),
    descripcion TEXT,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_tecnologia UNIQUE (nombre_tecnologia, categoria_tecnologia)
);


-- ==========================================================
-- DIMENSION: COMUNIDAD
-- Agrupa el contexto comunitario o canal de discusion asociado.
-- Representa propietarios, organizaciones, foros, instituciones o medios;
-- no reutiliza el nombre de plataforma como sustituto de comunidad.
-- ==========================================================
CREATE TABLE gold.dim_comunidad (
    id_comunidad BIGSERIAL PRIMARY KEY,
    nombre_comunidad VARCHAR(120) NOT NULL,
    tipo_comunidad VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL DEFAULT 'No especificado',
    plataforma_comunidad VARCHAR(100),
    descripcion TEXT,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_comunidad UNIQUE (nombre_comunidad, tipo_comunidad, plataforma_comunidad)
);


-- ==========================================================
-- TABLA DE HECHOS: ACTIVIDAD DE AGENTES DE IA
-- Una fila representa una actividad observada de adopcion o mencion
-- de un agente de IA en una fuente, plataforma y fecha determinada.
-- ==========================================================
CREATE TABLE gold.fact_actividad_agente_ia (
    id_fact_actividad BIGSERIAL PRIMARY KEY,

    id_tiempo BIGINT NOT NULL,
    id_agente BIGINT NOT NULL,
    id_fuente BIGINT NOT NULL,
    id_plataforma BIGINT NOT NULL,
    id_tecnologia BIGINT NOT NULL,
    id_comunidad BIGINT NOT NULL,

    id_origen_registro TEXT NOT NULL,
    raw_file_id INTEGER,
    -- FK is added by 02_raw_tables.sql after Raw exists in initdb order.
    raw_record_id INTEGER,
    fact_lineage_key TEXT NOT NULL,

    cantidad_menciones INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_menciones >= 0),
    cantidad_interacciones INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_interacciones >= 0),
    score_popularidad NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (score_popularidad >= 0),
    score_actividad NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (score_actividad >= 0),
    score_comunidad NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (score_comunidad >= 0),
    score_adopcion NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (score_adopcion >= 0),
    score_innovacion NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (score_innovacion >= 0),
    valor_numerico_normalizado NUMERIC(12,6),

    stars_github INTEGER NOT NULL DEFAULT 0 CHECK (stars_github >= 0),
    forks_github INTEGER NOT NULL DEFAULT 0 CHECK (forks_github >= 0),
    issues_abiertos INTEGER NOT NULL DEFAULT 0 CHECK (issues_abiertos >= 0),
    releases INTEGER NOT NULL DEFAULT 0 CHECK (releases >= 0),
    sentimiento_promedio NUMERIC(8,4),

    titulo TEXT,
    url VARCHAR(500),
    is_imputed_date BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_carga TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_fact_tiempo
        FOREIGN KEY (id_tiempo)
        REFERENCES gold.dim_tiempo (id_tiempo),
    CONSTRAINT fk_fact_agente
        FOREIGN KEY (id_agente)
        REFERENCES gold.dim_agente (id_agente),
    CONSTRAINT fk_fact_fuente
        FOREIGN KEY (id_fuente)
        REFERENCES gold.dim_fuente (id_fuente),
    CONSTRAINT fk_fact_plataforma
        FOREIGN KEY (id_plataforma)
        REFERENCES gold.dim_plataforma (id_plataforma),
    CONSTRAINT fk_fact_tecnologia
        FOREIGN KEY (id_tecnologia)
        REFERENCES gold.dim_tecnologia (id_tecnologia),
    CONSTRAINT fk_fact_comunidad
        FOREIGN KEY (id_comunidad)
        REFERENCES gold.dim_comunidad (id_comunidad),
    CONSTRAINT uq_fact_granularidad
        UNIQUE (
            id_agente,
            id_fuente,
            id_plataforma,
            id_origen_registro
        ),
    CONSTRAINT uq_fact_lineage_key UNIQUE (fact_lineage_key)
);


-- ==========================================================
-- INDICES PARA JOINS Y FILTROS ANALITICOS
-- ==========================================================

-- Dimension tiempo
CREATE INDEX idx_dim_tiempo_anio_mes
    ON gold.dim_tiempo (anio, mes);

CREATE INDEX idx_dim_tiempo_trimestre
    ON gold.dim_tiempo (anio, trimestre);

-- Dimension agente
CREATE INDEX idx_dim_agente_nombre
    ON gold.dim_agente (nombre_agente);

CREATE INDEX idx_dim_agente_categoria
    ON gold.dim_agente (categoria_agente);

-- Dimension fuente
CREATE INDEX idx_dim_fuente_tipo
    ON gold.dim_fuente (tipo_fuente);

CREATE INDEX idx_dim_fuente_categoria
    ON gold.dim_fuente (categoria_fuente);

-- Dimension plataforma
CREATE INDEX idx_dim_plataforma_tipo
    ON gold.dim_plataforma (tipo_plataforma);

-- Dimension tecnologia
CREATE INDEX idx_dim_tecnologia_dominio
    ON gold.dim_tecnologia (dominio_tecnologico);

CREATE INDEX idx_dim_tecnologia_tipo_senal
    ON gold.dim_tecnologia (tipo_senal);

-- Dimension comunidad
CREATE INDEX idx_dim_comunidad_tipo
    ON gold.dim_comunidad (tipo_comunidad);

CREATE INDEX idx_dim_comunidad_plataforma
    ON gold.dim_comunidad (plataforma_comunidad);

-- Tabla de hechos: llaves foraneas
CREATE INDEX idx_fact_id_tiempo
    ON gold.fact_actividad_agente_ia (id_tiempo);

CREATE INDEX idx_fact_id_agente
    ON gold.fact_actividad_agente_ia (id_agente);

CREATE INDEX idx_fact_id_fuente
    ON gold.fact_actividad_agente_ia (id_fuente);

CREATE INDEX idx_fact_id_plataforma
    ON gold.fact_actividad_agente_ia (id_plataforma);

CREATE INDEX idx_fact_id_tecnologia
    ON gold.fact_actividad_agente_ia (id_tecnologia);

CREATE INDEX idx_fact_id_comunidad
    ON gold.fact_actividad_agente_ia (id_comunidad);

-- Tabla de hechos: filtros y auditoria
CREATE INDEX idx_fact_origen_registro
    ON gold.fact_actividad_agente_ia (id_origen_registro);

CREATE INDEX idx_fact_raw_file_id
    ON gold.fact_actividad_agente_ia (raw_file_id);

CREATE INDEX idx_fact_raw_record_id
    ON gold.fact_actividad_agente_ia (raw_record_id);

CREATE INDEX idx_fact_scores
    ON gold.fact_actividad_agente_ia (
        score_popularidad,
        score_actividad,
        score_comunidad,
        score_adopcion
    );

CREATE INDEX idx_fact_metricas_tecnicas
    ON gold.fact_actividad_agente_ia (
        cantidad_menciones,
        cantidad_interacciones,
        stars_github,
        forks_github
    );
