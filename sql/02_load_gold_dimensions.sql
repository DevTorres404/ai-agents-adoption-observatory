-- ==========================================================
-- ENTREGABLE 4 - CARGA DE DIMENSIONES GOLD
-- Motor: PostgreSQL
--
-- Fuente unica permitida:
-- staging.stg_actividad_agente_ia
--
-- Este script pobla exclusivamente dimensiones. No consulta Raw, no
-- usa mock data y no crea registros ficticios. Los valores
-- "No especificado" se usan solo cuando Staging no posee una columna
-- o valor categorico no critico para completar el atributo dimensional.
-- ==========================================================

-- Carga idempotente: al reiniciar dimensiones tambien se limpia la
-- tabla de hechos por dependencia FK. La fact se cargara en un script
-- posterior desde Staging.
TRUNCATE TABLE
    gold.fact_actividad_agente_ia,
    gold.dim_tiempo,
    gold.dim_agente,
    gold.dim_fuente,
    gold.dim_plataforma,
    gold.dim_tecnologia,
    gold.dim_comunidad
RESTART IDENTITY CASCADE;


-- ==========================================================
-- 01. DIMENSION TIEMPO
-- Fuente: staging.stg_actividad_agente_ia.fecha_evento
-- ==========================================================
INSERT INTO gold.dim_tiempo (
    fecha,
    anio,
    semestre,
    trimestre,
    mes,
    nombre_mes,
    semana_anio,
    dia_mes,
    dia_semana,
    nombre_dia,
    es_fin_semana
)
SELECT DISTINCT
    s.fecha_evento AS fecha,
    EXTRACT(YEAR FROM s.fecha_evento)::SMALLINT AS anio,
    CASE
        WHEN EXTRACT(MONTH FROM s.fecha_evento)::INT BETWEEN 1 AND 6 THEN 1
        ELSE 2
    END::SMALLINT AS semestre,
    EXTRACT(QUARTER FROM s.fecha_evento)::SMALLINT AS trimestre,
    EXTRACT(MONTH FROM s.fecha_evento)::SMALLINT AS mes,
    CASE EXTRACT(MONTH FROM s.fecha_evento)::INT
        WHEN 1 THEN 'Enero'
        WHEN 2 THEN 'Febrero'
        WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril'
        WHEN 5 THEN 'Mayo'
        WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio'
        WHEN 8 THEN 'Agosto'
        WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'
        WHEN 12 THEN 'Diciembre'
    END AS nombre_mes,
    EXTRACT(WEEK FROM s.fecha_evento)::SMALLINT AS semana_anio,
    EXTRACT(DAY FROM s.fecha_evento)::SMALLINT AS dia_mes,
    EXTRACT(ISODOW FROM s.fecha_evento)::SMALLINT AS dia_semana,
    CASE EXTRACT(ISODOW FROM s.fecha_evento)::INT
        WHEN 1 THEN 'Lunes'
        WHEN 2 THEN 'Martes'
        WHEN 3 THEN 'Miercoles'
        WHEN 4 THEN 'Jueves'
        WHEN 5 THEN 'Viernes'
        WHEN 6 THEN 'Sabado'
        WHEN 7 THEN 'Domingo'
    END AS nombre_dia,
    (EXTRACT(ISODOW FROM s.fecha_evento)::INT IN (6, 7)) AS es_fin_semana
FROM staging.stg_actividad_agente_ia s
WHERE s.fecha_evento IS NOT NULL;


-- ==========================================================
-- 02. DIMENSION AGENTE
-- Fuente: nombre_agente y categoria desde Staging.
-- proveedor no existe en Staging; se conserva como No especificado.
-- ==========================================================
WITH agentes_distintos AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.nombre_agente), ''), 'No especificado') AS nombre_agente,
        COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado') AS categoria_agente
    FROM staging.stg_actividad_agente_ia s
    WHERE s.nombre_agente IS NOT NULL
),
agentes_consolidados AS (
    SELECT
        nombre_agente,
        MIN(categoria_agente) AS categoria_agente
    FROM agentes_distintos
    GROUP BY nombre_agente
)
INSERT INTO gold.dim_agente (
    nombre_agente,
    categoria_agente,
    tipo_agente,
    proveedor,
    es_agente_identificado
)
SELECT
    nombre_agente,
    categoria_agente,
    'No especificado' AS tipo_agente,
    'No especificado' AS proveedor,
    CASE
        WHEN nombre_agente IN ('Otro Agente IA', 'No especificado')
            THEN FALSE
        ELSE TRUE
    END AS es_agente_identificado
FROM agentes_consolidados;


-- ==========================================================
-- 03. DIMENSION FUENTE
-- Fuente: fuente y tipo_fuente desde Staging.
-- confiabilidad_fuente no existe en Staging; se conserva como No especificado.
-- ==========================================================
INSERT INTO gold.dim_fuente (
    nombre_fuente,
    tipo_fuente,
    categoria_fuente,
    confiabilidad_fuente,
    es_fuente_propia
)
SELECT DISTINCT
    COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') AS nombre_fuente,
    COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_fuente,
    COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS categoria_fuente,
    'No especificado' AS confiabilidad_fuente,
    (COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') = 'fuente_propia') AS es_fuente_propia
FROM staging.stg_actividad_agente_ia s
WHERE s.fuente IS NOT NULL
  AND s.tipo_fuente IS NOT NULL;


-- ==========================================================
-- 04. DIMENSION PLATAFORMA
-- Fuente: plataforma y tipo_fuente desde Staging.
-- ==========================================================
WITH plataformas_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS nombre_plataforma,
        COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_plataforma,
        COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') AS ecosistema
    FROM staging.stg_actividad_agente_ia s
    WHERE s.plataforma IS NOT NULL
)
INSERT INTO gold.dim_plataforma (
    nombre_plataforma,
    tipo_plataforma,
    ecosistema
)
SELECT
    nombre_plataforma,
    MIN(tipo_plataforma) AS tipo_plataforma,
    MIN(ecosistema) AS ecosistema
FROM plataformas_distintas
GROUP BY nombre_plataforma;


-- ==========================================================
-- 05. DIMENSION TECNOLOGIA
-- Fuente: categoria, tipo_fuente y plataforma desde Staging.
-- ==========================================================
WITH tecnologias_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado') AS nombre_tecnologia,
        COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado') AS categoria_tecnologia,
        COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS dominio_tecnologico,
        COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_senal
    FROM staging.stg_actividad_agente_ia s
    WHERE s.categoria IS NOT NULL
)
INSERT INTO gold.dim_tecnologia (
    nombre_tecnologia,
    categoria_tecnologia,
    dominio_tecnologico,
    tipo_senal
)
SELECT
    nombre_tecnologia,
    categoria_tecnologia,
    MIN(dominio_tecnologico) AS dominio_tecnologico,
    MIN(tipo_senal) AS tipo_senal
FROM tecnologias_distintas
GROUP BY nombre_tecnologia, categoria_tecnologia;


-- ==========================================================
-- 06. DIMENSION COMUNIDAD
-- Fuente: fuente, tipo_fuente y plataforma desde Staging.
-- region no existe en Staging; se conserva como No especificado.
-- ==========================================================
WITH comunidades_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS nombre_comunidad,
        COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_comunidad,
        'No especificado' AS region,
        COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS plataforma_comunidad
    FROM staging.stg_actividad_agente_ia s
    WHERE s.plataforma IS NOT NULL
)
INSERT INTO gold.dim_comunidad (
    nombre_comunidad,
    tipo_comunidad,
    region,
    plataforma_comunidad
)
SELECT
    nombre_comunidad,
    MIN(tipo_comunidad) AS tipo_comunidad,
    MIN(region) AS region,
    plataforma_comunidad
FROM comunidades_distintas
GROUP BY nombre_comunidad, plataforma_comunidad;


-- ==========================================================
-- VALIDACIONES FINALES
-- ==========================================================
SELECT
    'gold.dim_tiempo' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_tiempo
UNION ALL
SELECT
    'gold.dim_agente' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_agente
UNION ALL
SELECT
    'gold.dim_fuente' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_fuente
UNION ALL
SELECT
    'gold.dim_plataforma' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_plataforma
UNION ALL
SELECT
    'gold.dim_tecnologia' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_tecnologia
UNION ALL
SELECT
    'gold.dim_comunidad' AS tabla,
    COUNT(*) AS total_registros
FROM gold.dim_comunidad
ORDER BY tabla;
