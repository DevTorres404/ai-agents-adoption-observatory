-- Tablas de la Zona Staging (Limpieza y Tipado Estricto)

DROP TABLE IF EXISTS staging.stg_actividad_agente_ia CASCADE;

CREATE TABLE staging.stg_actividad_agente_ia (
    id SERIAL PRIMARY KEY,
    id_origen_registro VARCHAR(255) NOT NULL,
    fuente VARCHAR(100) NOT NULL,
    tipo_fuente VARCHAR(50) NOT NULL,
    plataforma VARCHAR(100) NOT NULL,
    fecha_evento DATE NOT NULL,
    nombre_agente VARCHAR(100) NOT NULL,
    categoria VARCHAR(100) NOT NULL,
    titulo TEXT,
    texto TEXT,
    url VARCHAR(500),
    cantidad_menciones INTEGER DEFAULT 0,
    cantidad_interacciones INTEGER DEFAULT 0,
    score_popularidad NUMERIC(10,2) DEFAULT 0.0,
    stars_github INTEGER,
    forks_github INTEGER,
    issues_abiertos INTEGER,
    releases INTEGER,
    indice_adopcion NUMERIC(5,2),
    indice_innovacion NUMERIC(5,2),
    sentimiento_promedio NUMERIC(5,2),
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_file_id INTEGER REFERENCES raw.raw_files(id),
    UNIQUE(fuente, plataforma, id_origen_registro, nombre_agente, fecha_evento)
);
