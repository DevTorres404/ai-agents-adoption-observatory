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
    fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    run_id INTEGER REFERENCES audit.pipeline_runs(run_id)
);

CREATE TABLE raw.raw_records (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES raw.raw_files(id) ON DELETE CASCADE,
    raw_data JSONB NOT NULL,
    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    run_id INTEGER REFERENCES audit.pipeline_runs(run_id)
);

-- Gold is initialized before Raw by filename order, so its lineage FK can
-- only be attached after raw.raw_records exists.
DO $$
BEGIN
    IF to_regclass('gold.fact_actividad_agente_ia') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conname = 'fk_fact_raw_record'
             AND conrelid = 'gold.fact_actividad_agente_ia'::regclass
       ) THEN
        ALTER TABLE gold.fact_actividad_agente_ia
            ADD CONSTRAINT fk_fact_raw_record
            FOREIGN KEY (raw_record_id) REFERENCES raw.raw_records(id);
    END IF;
END $$;
