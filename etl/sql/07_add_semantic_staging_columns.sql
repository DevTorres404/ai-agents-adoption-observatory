-- Migración idempotente para instalaciones existentes.
-- Una instalación nueva ya recibe estas columnas desde 03_staging_tables.sql.

ALTER TABLE staging.stg_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS is_imputed_date BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS dim_nombre_plataforma VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_tipo_plataforma VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_ecosistema VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_plataforma_metodo VARCHAR(50),
    ADD COLUMN IF NOT EXISTS dim_nombre_tecnologia VARCHAR(120),
    ADD COLUMN IF NOT EXISTS dim_categoria_tecnologia VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_dominio_tecnologico VARCHAR(120),
    ADD COLUMN IF NOT EXISTS dim_tipo_senal VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_tecnologia_metodo VARCHAR(50),
    ADD COLUMN IF NOT EXISTS dim_nombre_comunidad VARCHAR(120),
    ADD COLUMN IF NOT EXISTS dim_tipo_comunidad VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_region_comunidad VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dim_comunidad_metodo VARCHAR(50);

-- Los identificadores de algunas fuentes (por ejemplo, URLs canónicas de
-- Google News) superan 255 caracteres. Se conservan completos para no generar
-- colisiones por truncamiento.
ALTER TABLE staging.stg_actividad_agente_ia
    ALTER COLUMN id_origen_registro TYPE TEXT;

-- Compatibilidad con instalaciones creadas antes de incorporar la trazabilidad
-- de fechas imputadas al contrato de la tabla de hechos.
ALTER TABLE gold.fact_actividad_agente_ia
    ADD COLUMN IF NOT EXISTS is_imputed_date BOOLEAN DEFAULT FALSE;

ALTER TABLE gold.fact_actividad_agente_ia
    ALTER COLUMN id_origen_registro TYPE TEXT;

-- La fecha y las clasificaciones semánticas describen la observación, pero no
-- identifican a la entidad de origen. Estas restricciones alinean la BD con la
-- deduplicación estable aplicada por el ETL.
ALTER TABLE staging.stg_actividad_agente_ia
    DROP CONSTRAINT IF EXISTS stg_actividad_agente_ia_fuente_plataforma_id_origen_registr_key,
    DROP CONSTRAINT IF EXISTS uq_staging_entidad_estable;

ALTER TABLE staging.stg_actividad_agente_ia
    ADD CONSTRAINT uq_staging_entidad_estable
    UNIQUE (fuente, plataforma, id_origen_registro, nombre_agente);

ALTER TABLE gold.fact_actividad_agente_ia
    DROP CONSTRAINT IF EXISTS uq_fact_granularidad;

ALTER TABLE gold.fact_actividad_agente_ia
    ADD CONSTRAINT uq_fact_granularidad
    UNIQUE (id_agente, id_fuente, id_plataforma, id_origen_registro);
