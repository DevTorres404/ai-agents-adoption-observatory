-- ==========================================================
-- ENTREGABLE 4 - VALIDACION AUDITABLE DATA WAREHOUSE GOLD
-- Motor: PostgreSQL
--
-- Objetivo:
-- Generar evidencia verificable del modelo dimensional Gold para ser
-- copiada en el documento academico UPSE.
--
-- Nota:
-- Este script consulta Staging solo para comparar el total de registros
-- fuente contra la tabla de hechos Gold. Las demas validaciones se
-- realizan sobre el esquema gold.
-- ==========================================================


-- ==========================================================
-- 00. Fecha de validacion
-- ==========================================================
SELECT
    CURRENT_DATE AS fecha_validacion_gold_dw;


-- ==========================================================
-- 01. Total de registros por tabla Gold
-- ==========================================================
SELECT
    'gold.dim_tiempo' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_tiempo
UNION ALL
SELECT
    'gold.dim_agente' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_agente
UNION ALL
SELECT
    'gold.dim_fuente' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_fuente
UNION ALL
SELECT
    'gold.dim_plataforma' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_plataforma
UNION ALL
SELECT
    'gold.dim_tecnologia' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_tecnologia
UNION ALL
SELECT
    'gold.dim_comunidad' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.dim_comunidad
UNION ALL
SELECT
    'gold.fact_actividad_agente_ia' AS tabla_gold,
    COUNT(*) AS total_registros
FROM gold.fact_actividad_agente_ia
ORDER BY tabla_gold;


-- ==========================================================
-- 02. Comparacion Staging vs Fact Gold
-- ==========================================================
WITH conteos AS (
    SELECT
        (SELECT COUNT(*) FROM staging.stg_actividad_agente_ia) AS total_staging,
        (SELECT COUNT(*) FROM gold.fact_actividad_agente_ia) AS total_fact_gold
)
SELECT
    total_staging,
    total_fact_gold,
    ABS(total_staging - total_fact_gold) AS diferencia_absoluta,
    ROUND(
        ABS(total_staging - total_fact_gold) * 100.0 / NULLIF(total_staging, 0),
        4
    ) AS porcentaje_merma
FROM conteos;


-- ==========================================================
-- 03. Verificacion de integridad referencial
-- Si el modelo esta correctamente cargado, todos los conteos deben ser 0.
-- ==========================================================
SELECT
    SUM(CASE WHEN da.id_agente IS NULL THEN 1 ELSE 0 END) AS hechos_sin_agente,
    SUM(CASE WHEN df.id_fuente IS NULL THEN 1 ELSE 0 END) AS hechos_sin_fuente,
    SUM(CASE WHEN dt.id_tiempo IS NULL THEN 1 ELSE 0 END) AS hechos_sin_tiempo,
    SUM(CASE WHEN dp.id_plataforma IS NULL THEN 1 ELSE 0 END) AS hechos_sin_plataforma,
    SUM(CASE WHEN dtec.id_tecnologia IS NULL THEN 1 ELSE 0 END) AS hechos_sin_tecnologia,
    SUM(CASE WHEN dc.id_comunidad IS NULL THEN 1 ELSE 0 END) AS hechos_sin_comunidad
FROM gold.fact_actividad_agente_ia f
LEFT JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
LEFT JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
LEFT JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
LEFT JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
LEFT JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
LEFT JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad;


-- ==========================================================
-- 04. Distribucion de hechos por fuente
-- ==========================================================
SELECT
    df.nombre_fuente,
    df.tipo_fuente,
    COUNT(*) AS total_hechos,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_participacion
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
GROUP BY df.nombre_fuente, df.tipo_fuente
ORDER BY total_hechos DESC, df.nombre_fuente;


-- ==========================================================
-- 05. Distribucion de hechos por agente
-- ==========================================================
SELECT
    da.nombre_agente,
    da.categoria_agente,
    COUNT(*) AS total_hechos,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_participacion
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
GROUP BY da.nombre_agente, da.categoria_agente
ORDER BY total_hechos DESC, da.nombre_agente;


-- ==========================================================
-- 06. Rango minimo y maximo de fechas cargadas en Gold
-- ==========================================================
SELECT
    MIN(dt.fecha) AS fecha_minima_gold,
    MAX(dt.fecha) AS fecha_maxima_gold,
    MIN(dt.anio) AS anio_minimo_gold,
    MAX(dt.anio) AS anio_maximo_gold,
    COUNT(DISTINCT dt.fecha) AS fechas_distintas_cargadas
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo;


-- ==========================================================
-- 07. Validacion del periodo academico 2023-2026
-- Confirma que Staging y Gold contienen datos dentro del periodo
-- definido para el proyecto y que no existen hechos fuera de rango.
-- ==========================================================
SELECT
    'staging' AS capa,
    COUNT(*) AS total_registros,
    MIN(fecha_evento) AS fecha_minima,
    MAX(fecha_evento) AS fecha_maxima,
    COUNT(*) FILTER (
        WHERE fecha_evento < DATE '2023-01-01'
           OR fecha_evento > DATE '2026-12-31'
    ) AS registros_fuera_periodo,
    CASE
        WHEN COUNT(*) FILTER (
            WHERE fecha_evento < DATE '2023-01-01'
               OR fecha_evento > DATE '2026-12-31'
        ) = 0
            THEN 'VALIDO: periodo 2023-2026'
        ELSE 'REVISAR: existen registros fuera del periodo'
    END AS estado_validacion
FROM staging.stg_actividad_agente_ia
UNION ALL
SELECT
    'gold' AS capa,
    COUNT(*) AS total_registros,
    MIN(dt.fecha) AS fecha_minima,
    MAX(dt.fecha) AS fecha_maxima,
    COUNT(*) FILTER (
        WHERE dt.fecha < DATE '2023-01-01'
           OR dt.fecha > DATE '2026-12-31'
    ) AS registros_fuera_periodo,
    CASE
        WHEN COUNT(*) FILTER (
            WHERE dt.fecha < DATE '2023-01-01'
               OR dt.fecha > DATE '2026-12-31'
        ) = 0
            THEN 'VALIDO: periodo 2023-2026'
        ELSE 'REVISAR: existen registros fuera del periodo'
    END AS estado_validacion
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
ORDER BY capa;


-- ==========================================================
-- 08. Validacion de que las vistas KPI devuelven resultados
-- ==========================================================
SELECT
    'gold.vw_kpi_adopcion_por_agente' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_adopcion_por_agente
UNION ALL
SELECT
    'gold.vw_kpi_participacion_por_fuente' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_participacion_por_fuente
UNION ALL
SELECT
    'gold.vw_kpi_tendencia_mensual' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_tendencia_mensual
UNION ALL
SELECT
    'gold.vw_kpi_ranking_agentes' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_ranking_agentes
UNION ALL
SELECT
    'gold.vw_kpi_popularidad_open_source' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_popularidad_open_source
UNION ALL
SELECT
    'gold.vw_kpi_crecimiento_mensual' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_crecimiento_mensual
UNION ALL
SELECT
    'gold.vw_kpi_distribucion_por_plataforma' AS vista_kpi,
    COUNT(*) AS total_filas
FROM gold.vw_kpi_distribucion_por_plataforma
ORDER BY vista_kpi;


-- ==========================================================
-- 09. Muestra auditable de resultados KPI
-- Estas consultas permiten capturar evidencia visual o tabular rapida.
-- ==========================================================
SELECT * FROM gold.vw_kpi_adopcion_por_agente LIMIT 10;
SELECT * FROM gold.vw_kpi_participacion_por_fuente LIMIT 10;
SELECT * FROM gold.vw_kpi_tendencia_mensual LIMIT 10;
SELECT * FROM gold.vw_kpi_ranking_agentes LIMIT 10;
SELECT * FROM gold.vw_kpi_popularidad_open_source LIMIT 10;
SELECT * FROM gold.vw_kpi_crecimiento_mensual LIMIT 10;
SELECT * FROM gold.vw_kpi_distribucion_por_plataforma LIMIT 10;
