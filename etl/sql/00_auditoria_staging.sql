-- ==========================================================
-- ENTREGABLE 4 - AUDITORIA DE STAGING
-- Proyecto: Observatorio / Plataforma BI sobre adopcion de agentes de IA
-- Motor: PostgreSQL
--
-- Objetivo:
-- Validar el estado tecnico de la tabla staging.stg_actividad_agente_ia
-- antes de construir el Data Warehouse dimensional.
--
-- Restriccion academica:
-- Todas las metricas de datos se calculan exclusivamente desde
-- staging.stg_actividad_agente_ia. No se consulta Raw ni se usan datos
-- ficticios o tablas auxiliares para los conteos.
-- ==========================================================

SELECT '00. Tabla auditada' AS seccion;
SELECT
    'staging.stg_actividad_agente_ia' AS tabla_auditada,
    CURRENT_TIMESTAMP AS fecha_auditoria;


SELECT '01. Total de registros en Staging' AS seccion;
SELECT
    COUNT(*) AS total_registros_staging
FROM staging.stg_actividad_agente_ia;


SELECT '02. Columnas disponibles y tipos de datos' AS seccion;
SELECT
    ordinal_position,
    column_name,
    CASE
        WHEN character_maximum_length IS NOT NULL
            THEN data_type || '(' || character_maximum_length || ')'
        WHEN numeric_precision IS NOT NULL AND numeric_scale IS NOT NULL
            THEN data_type || '(' || numeric_precision || ',' || numeric_scale || ')'
        ELSE data_type
    END AS tipo_dato,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'staging'
  AND table_name = 'stg_actividad_agente_ia'
ORDER BY ordinal_position;


SELECT '03. Cantidad de fuentes distintas' AS seccion;
SELECT
    COUNT(DISTINCT fuente) AS fuentes_distintas,
    COUNT(DISTINCT tipo_fuente) AS tipos_fuente_distintos,
    COUNT(DISTINCT plataforma) AS plataformas_distintas
FROM staging.stg_actividad_agente_ia;


SELECT '04. Cantidad de agentes de IA distintos' AS seccion;
SELECT
    COUNT(DISTINCT nombre_agente) AS agentes_ia_distintos
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(nombre_agente), '') IS NOT NULL;


SELECT '05. Rango minimo y maximo de fechas' AS seccion;
SELECT
    MIN(fecha_evento) AS fecha_minima,
    MAX(fecha_evento) AS fecha_maxima,
    (MAX(fecha_evento) - MIN(fecha_evento)) AS dias_cubiertos
FROM staging.stg_actividad_agente_ia;


SELECT '05.1. Validacion del periodo academico 2023-2026' AS seccion;
SELECT
    DATE '2023-01-01' AS fecha_inicio_esperada,
    DATE '2026-12-31' AS fecha_fin_esperada,
    MIN(fecha_evento) AS fecha_minima_real,
    MAX(fecha_evento) AS fecha_maxima_real,
    COUNT(*) AS total_registros_staging,
    COUNT(*) FILTER (
        WHERE fecha_evento < DATE '2023-01-01'
           OR fecha_evento > DATE '2026-12-31'
    ) AS registros_fuera_periodo,
    CASE
        WHEN COUNT(*) FILTER (
            WHERE fecha_evento < DATE '2023-01-01'
               OR fecha_evento > DATE '2026-12-31'
        ) = 0
            THEN 'VALIDO: todos los registros pertenecen al periodo 2023-2026'
        ELSE 'REVISAR: existen registros fuera del periodo 2023-2026'
    END AS estado_validacion
FROM staging.stg_actividad_agente_ia;


SELECT '06. Nulos criticos por columna importante' AS seccion;
SELECT 'id_origen_registro' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(id_origen_registro), '') IS NULL
UNION ALL
SELECT 'fuente' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(fuente), '') IS NULL
UNION ALL
SELECT 'tipo_fuente' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(tipo_fuente), '') IS NULL
UNION ALL
SELECT 'plataforma' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(plataforma), '') IS NULL
UNION ALL
SELECT 'fecha_evento' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE fecha_evento IS NULL
UNION ALL
SELECT 'nombre_agente' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(nombre_agente), '') IS NULL
UNION ALL
SELECT 'categoria' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE NULLIF(BTRIM(categoria), '') IS NULL
UNION ALL
SELECT 'raw_file_id' AS columna, COUNT(*) AS registros_nulos_o_vacios
FROM staging.stg_actividad_agente_ia
WHERE raw_file_id IS NULL
ORDER BY columna;


SELECT '07. Resumen de posibles duplicados por clave analitica' AS seccion;
WITH duplicados AS (
    SELECT
        fuente,
        plataforma,
        id_origen_registro,
        nombre_agente,
        fecha_evento,
        COUNT(*) AS cantidad
    FROM staging.stg_actividad_agente_ia
    GROUP BY
        fuente,
        plataforma,
        id_origen_registro,
        nombre_agente,
        fecha_evento
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(*) AS grupos_duplicados,
    COALESCE(SUM(cantidad), 0) AS registros_en_grupos_duplicados,
    COALESCE(SUM(cantidad - 1), 0) AS duplicados_excedentes
FROM duplicados;


SELECT '07b. Detalle de posibles duplicados por clave analitica' AS seccion;
SELECT
    fuente,
    plataforma,
    id_origen_registro,
    nombre_agente,
    fecha_evento,
    COUNT(*) AS cantidad
FROM staging.stg_actividad_agente_ia
GROUP BY
    fuente,
    plataforma,
    id_origen_registro,
    nombre_agente,
    fecha_evento
HAVING COUNT(*) > 1
ORDER BY cantidad DESC, fuente, plataforma, nombre_agente, fecha_evento;


SELECT '08. Distribucion de registros por fuente' AS seccion;
SELECT
    fuente,
    tipo_fuente,
    plataforma,
    COUNT(*) AS total_registros,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_staging
FROM staging.stg_actividad_agente_ia
GROUP BY fuente, tipo_fuente, plataforma
ORDER BY total_registros DESC, fuente, plataforma;


SELECT '09. Distribucion de registros por agente' AS seccion;
SELECT
    nombre_agente,
    COUNT(*) AS total_registros,
    COUNT(DISTINCT fuente) AS fuentes_asociadas,
    MIN(fecha_evento) AS primera_fecha,
    MAX(fecha_evento) AS ultima_fecha,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_staging
FROM staging.stg_actividad_agente_ia
GROUP BY nombre_agente
ORDER BY total_registros DESC, nombre_agente;


SELECT '10. Validacion de procedencia: auditoria ejecutada sobre Staging' AS seccion;
SELECT
    'staging.stg_actividad_agente_ia' AS tabla_consultada,
    COUNT(*) AS registros_auditados,
    COUNT(raw_file_id) AS registros_con_referencia_raw_file_id,
    COUNT(*) - COUNT(raw_file_id) AS registros_sin_referencia_raw_file_id,
    COUNT(DISTINCT raw_file_id) AS archivos_raw_referenciados_desde_staging
FROM staging.stg_actividad_agente_ia;


SELECT '10b. Control adicional de procedencia por fuente dentro de Staging' AS seccion;
SELECT
    fuente,
    COUNT(*) AS registros_staging,
    COUNT(raw_file_id) AS registros_con_raw_file_id,
    COUNT(*) - COUNT(raw_file_id) AS registros_sin_raw_file_id,
    COUNT(DISTINCT raw_file_id) AS raw_file_id_distintos
FROM staging.stg_actividad_agente_ia
GROUP BY fuente
ORDER BY registros_staging DESC, fuente;
