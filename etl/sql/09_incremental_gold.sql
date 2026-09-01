-- Idempotent migration for stable, incremental Gold loading.

ALTER TABLE gold.fact_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS raw_record_id INTEGER;

ALTER TABLE gold.fact_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS fact_lineage_key TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
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

UPDATE gold.fact_actividad_agente_ia
SET fact_lineage_key = CASE
    WHEN raw_record_id IS NOT NULL THEN 'raw:' || raw_record_id::TEXT
    ELSE 'legacy:' || id_fact_actividad::TEXT
END
WHERE fact_lineage_key IS NULL;

ALTER TABLE gold.fact_actividad_agente_ia
    ALTER COLUMN fact_lineage_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_tiempo_fecha_idx
    ON gold.dim_tiempo (fecha);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_agente_nombre_idx
    ON gold.dim_agente (nombre_agente);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_fuente_natural_idx
    ON gold.dim_fuente (nombre_fuente, tipo_fuente);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_plataforma_nombre_idx
    ON gold.dim_plataforma (nombre_plataforma);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_tecnologia_natural_idx
    ON gold.dim_tecnologia (nombre_tecnologia, categoria_tecnologia);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_comunidad_natural_idx
    ON gold.dim_comunidad (nombre_comunidad, tipo_comunidad, plataforma_comunidad);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_lineage_key_idx
    ON gold.fact_actividad_agente_ia (fact_lineage_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_business_grain_idx
    ON gold.fact_actividad_agente_ia
       (id_agente, id_fuente, id_plataforma, id_origen_registro);

CREATE INDEX IF NOT EXISTS idx_fact_raw_record_id
    ON gold.fact_actividad_agente_ia (raw_record_id);
