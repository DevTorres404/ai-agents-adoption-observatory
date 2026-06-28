-- Tablas de la Zona Raw (Inmutables con Auditoría)

DROP TABLE IF EXISTS raw.raw_records CASCADE;
DROP TABLE IF EXISTS raw.raw_files CASCADE;

CREATE TABLE raw.raw_files (
    id SERIAL PRIMARY KEY,
    fuente VARCHAR(100) NOT NULL,
    tipo_fuente VARCHAR(50) NOT NULL,
    ruta_relativa VARCHAR(500) NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    fecha_extraccion TIMESTAMP,
    cantidad_registros INTEGER,
    cantidad_columnas INTEGER,
    tamano_bytes INTEGER,
    hash_sha256 VARCHAR(64) UNIQUE NOT NULL,
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE raw.raw_records (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES raw.raw_files(id) ON DELETE CASCADE,
    raw_data JSONB NOT NULL,
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
