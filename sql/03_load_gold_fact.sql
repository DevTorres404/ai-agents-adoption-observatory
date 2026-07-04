-- ==========================================================
-- ENTREGABLE 4 - CARGA DE TABLA DE HECHOS GOLD
-- Motor: PostgreSQL
--
-- Fuente unica permitida:
-- staging.stg_actividad_agente_ia
--
-- Este script pobla gold.fact_actividad_agente_ia mediante JOINs
-- explicitos contra las dimensiones Gold. No consulta Raw, no usa
-- mock data y no inserta datos simulados.
--
-- Granularidad:
-- Un registro representa una actividad observada de adopcion o mencion
-- de un agente de IA en una fuente, plataforma y fecha determinada.
-- ==========================================================

TRUNCATE TABLE gold.fact_actividad_agente_ia RESTART IDENTITY;


-- ==========================================================
-- CARGA DE HECHOS
-- ==========================================================
-- Derivaciones documentadas:
-- 1. score_actividad:
--    Staging no posee una columna con ese nombre. Se deriva sumando
--    cantidad_interacciones y senales tecnicas GitHub disponibles
--    (stars, forks, issues y releases).
--
-- 2. score_comunidad:
--    Staging no posee una columna con ese nombre. Se deriva desde
--    cantidad_menciones + cantidad_interacciones solo para registros
--    clasificados como comunidad o provenientes de fuentes comunitarias
--    (reddit, hackernews, devto). En otros casos se registra 0.
--
-- 3. score_adopcion y score_innovacion:
--    Se cargan desde indice_adopcion e indice_innovacion de Staging.
--
-- 4. valor_numerico_normalizado:
--    Staging no posee una columna unica con ese nombre. Se conserva el
--    primer indicador analitico disponible en este orden:
--    score_popularidad, indice_adopcion, indice_innovacion,
--    cantidad_interacciones, cantidad_menciones.
-- ==========================================================

INSERT INTO gold.fact_actividad_agente_ia (
    id_tiempo,
    id_agente,
    id_fuente,
    id_plataforma,
    id_tecnologia,
    id_comunidad,
    id_origen_registro,
    raw_file_id,
    cantidad_menciones,
    cantidad_interacciones,
    score_popularidad,
    score_actividad,
    score_comunidad,
    score_adopcion,
    score_innovacion,
    valor_numerico_normalizado,
    stars_github,
    forks_github,
    issues_abiertos,
    releases,
    sentimiento_promedio,
    titulo,
    url
)
SELECT
    dt.id_tiempo,
    da.id_agente,
    df.id_fuente,
    dp.id_plataforma,
    dtec.id_tecnologia,
    dc.id_comunidad,
    s.id_origen_registro,
    s.raw_file_id,

    COALESCE(s.cantidad_menciones, 0) AS cantidad_menciones,
    COALESCE(s.cantidad_interacciones, 0) AS cantidad_interacciones,
    COALESCE(s.score_popularidad, 0)::NUMERIC(12,4) AS score_popularidad,

    (
        COALESCE(s.cantidad_interacciones, 0)
        + COALESCE(s.stars_github, 0)
        + COALESCE(s.forks_github, 0)
        + COALESCE(s.issues_abiertos, 0)
        + COALESCE(s.releases, 0)
    )::NUMERIC(12,4) AS score_actividad,

    CASE
        WHEN COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado') = 'comunidad'
          OR COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') IN ('reddit', 'hackernews', 'devto')
            THEN (
                COALESCE(s.cantidad_menciones, 0)
                + COALESCE(s.cantidad_interacciones, 0)
            )::NUMERIC(12,4)
        ELSE 0::NUMERIC(12,4)
    END AS score_comunidad,

    COALESCE(s.indice_adopcion, 0)::NUMERIC(12,4) AS score_adopcion,
    COALESCE(s.indice_innovacion, 0)::NUMERIC(12,4) AS score_innovacion,
    COALESCE(
        s.score_popularidad,
        s.indice_adopcion,
        s.indice_innovacion,
        s.cantidad_interacciones::NUMERIC,
        s.cantidad_menciones::NUMERIC
    )::NUMERIC(12,6) AS valor_numerico_normalizado,

    COALESCE(s.stars_github, 0) AS stars_github,
    COALESCE(s.forks_github, 0) AS forks_github,
    COALESCE(s.issues_abiertos, 0) AS issues_abiertos,
    COALESCE(s.releases, 0) AS releases,
    s.sentimiento_promedio,
    s.titulo,
    s.url
FROM staging.stg_actividad_agente_ia s
INNER JOIN gold.dim_tiempo dt
    ON dt.fecha = s.fecha_evento
INNER JOIN gold.dim_agente da
    ON da.nombre_agente = COALESCE(NULLIF(BTRIM(s.nombre_agente), ''), 'No especificado')
INNER JOIN gold.dim_fuente df
    ON df.nombre_fuente = COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado')
   AND df.tipo_fuente = COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado')
INNER JOIN gold.dim_plataforma dp
    ON dp.nombre_plataforma = COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado')
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.nombre_tecnologia = COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado')
   AND dtec.categoria_tecnologia = COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado')
INNER JOIN gold.dim_comunidad dc
    ON dc.nombre_comunidad = COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado')
   AND dc.plataforma_comunidad = COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado')
WHERE s.id_origen_registro IS NOT NULL
  AND s.fecha_evento IS NOT NULL
  AND s.nombre_agente IS NOT NULL
  AND s.fuente IS NOT NULL
  AND s.tipo_fuente IS NOT NULL
  AND s.plataforma IS NOT NULL
  AND s.categoria IS NOT NULL
ON CONFLICT ON CONSTRAINT uq_fact_granularidad DO NOTHING;


-- ==========================================================
-- VALIDACIONES FINALES
-- ==========================================================

-- Total de registros disponibles en Staging.
WITH conteos AS (
    SELECT
        (SELECT COUNT(*) FROM staging.stg_actividad_agente_ia) AS total_staging,
        (SELECT COUNT(*) FROM gold.fact_actividad_agente_ia) AS total_fact
)
SELECT
    total_staging,
    total_fact,
    ABS(total_staging - total_fact) AS diferencia_absoluta,
    ROUND(
        ABS(total_staging - total_fact) * 100.0 / NULLIF(total_staging, 0),
        4
    ) AS porcentaje_merma
FROM conteos;


-- Conteo de hechos sin dimension relacionada.
-- Por definicion, con FKs e INNER JOINs deberia devolver 0 en todos
-- los campos. Se deja como evidencia de integridad dimensional.
SELECT
    SUM(CASE WHEN dt.id_tiempo IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_tiempo,
    SUM(CASE WHEN da.id_agente IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_agente,
    SUM(CASE WHEN df.id_fuente IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_fuente,
    SUM(CASE WHEN dp.id_plataforma IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_plataforma,
    SUM(CASE WHEN dtec.id_tecnologia IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_tecnologia,
    SUM(CASE WHEN dc.id_comunidad IS NULL THEN 1 ELSE 0 END) AS hechos_sin_dim_comunidad
FROM gold.fact_actividad_agente_ia f
LEFT JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
LEFT JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
LEFT JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
LEFT JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
LEFT JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
LEFT JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad;


-- Validacion adicional: distribucion de hechos por fuente y agente.
SELECT
    df.nombre_fuente,
    da.nombre_agente,
    COUNT(*) AS total_hechos
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
GROUP BY df.nombre_fuente, da.nombre_agente
ORDER BY total_hechos DESC, df.nombre_fuente, da.nombre_agente;

