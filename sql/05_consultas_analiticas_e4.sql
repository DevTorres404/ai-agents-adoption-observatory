-- ==========================================================
-- ENTREGABLE 4 - CONSULTAS ANALITICAS
-- Proyecto BI: Observatorio sobre adopcion de agentes de IA
-- Motor: PostgreSQL
--
-- Restriccion academica:
-- Todas las consultas se ejecutan exclusivamente sobre el esquema gold.
-- No se consulta Raw ni Staging directamente.
-- ==========================================================


-- ==========================================================
-- PREGUNTA PRINCIPAL 1:
-- Cual es el nivel de adopcion de agentes de IA en el desarrollo
-- de software durante el periodo 2023-2026?
-- ==========================================================
SELECT
    MIN(dt.fecha) AS fecha_inicio_observada,
    MAX(dt.fecha) AS fecha_fin_observada,
    COUNT(*) AS total_observaciones,
    COUNT(DISTINCT da.id_agente) AS agentes_distintos,
    COUNT(DISTINCT df.id_fuente) AS fuentes_distintas,
    COUNT(DISTINCT dp.id_plataforma) AS plataformas_distintas,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(AVG(f.score_adopcion), 4) AS promedio_score_adopcion,
    ROUND(SUM(f.score_adopcion), 4) AS score_adopcion_total,
    ROUND(AVG(f.valor_numerico_normalizado), 4) AS promedio_valor_normalizado
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
INNER JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad
WHERE dt.anio BETWEEN 2023 AND 2026;
-- Guia de interpretacion:
-- Un mayor promedio de score_adopcion, junto con alto volumen de
-- observaciones, menciones e interacciones, indica mayor nivel general
-- de adopcion durante el periodo analizado.


-- ==========================================================
-- PREGUNTA SECUNDARIA 2:
-- Que agentes de IA presentan mayor nivel de adopcion?
-- Consulta Top 10 con ranking.
-- ==========================================================
SELECT
    da.nombre_agente,
    da.categoria_agente,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(AVG(f.score_adopcion), 4) AS promedio_score_adopcion,
    ROUND(SUM(f.score_adopcion), 4) AS score_adopcion_total,
    RANK() OVER (
        ORDER BY SUM(f.score_adopcion) DESC, COUNT(*) DESC
    ) AS ranking_adopcion
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
INNER JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad
WHERE dt.anio BETWEEN 2023 AND 2026
GROUP BY da.nombre_agente, da.categoria_agente
ORDER BY ranking_adopcion, score_adopcion_total DESC
LIMIT 10;
-- Guia de interpretacion:
-- Los agentes en las primeras posiciones concentran mayor senal de
-- adopcion acumulada. Si un agente tiene alto score y muchas
-- observaciones, su adopcion es mas consistente dentro del DW.


-- ==========================================================
-- PREGUNTA SECUNDARIA 3:
-- Que fuentes digitales evidencian mayor actividad sobre agentes de IA?
-- Consulta con participacion porcentual por fuente.
-- ==========================================================
SELECT
    df.nombre_fuente,
    df.tipo_fuente,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(SUM(f.score_actividad), 4) AS score_actividad_total,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_observaciones,
    ROUND(
        SUM(f.score_actividad) * 100.0 / NULLIF(SUM(SUM(f.score_actividad)) OVER (), 0),
        2
    ) AS porcentaje_actividad
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
INNER JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad
WHERE dt.anio BETWEEN 2023 AND 2026
GROUP BY df.nombre_fuente, df.tipo_fuente
ORDER BY score_actividad_total DESC, total_observaciones DESC;
-- Guia de interpretacion:
-- Las fuentes con mayor porcentaje de actividad son las que aportan
-- mas evidencia analitica sobre agentes de IA. Una concentracion alta
-- en una fuente debe considerarse al interpretar sesgos del dataset.


-- ==========================================================
-- PREGUNTA SECUNDARIA 4:
-- Como evoluciona mensualmente la adopcion de agentes de IA?
-- Consulta de evolucion temporal mensual con LAG.
-- ==========================================================
WITH adopcion_mensual AS (
    SELECT
        dt.anio,
        dt.mes,
        dt.nombre_mes,
        COUNT(*) AS total_observaciones,
        SUM(f.cantidad_menciones) AS total_menciones,
        SUM(f.cantidad_interacciones) AS total_interacciones,
        ROUND(AVG(f.score_adopcion), 4) AS promedio_score_adopcion,
        ROUND(SUM(f.score_adopcion), 4) AS score_adopcion_total
    FROM gold.fact_actividad_agente_ia f
    INNER JOIN gold.dim_tiempo dt
        ON dt.id_tiempo = f.id_tiempo
    INNER JOIN gold.dim_agente da
        ON da.id_agente = f.id_agente
    INNER JOIN gold.dim_fuente df
        ON df.id_fuente = f.id_fuente
    INNER JOIN gold.dim_plataforma dp
        ON dp.id_plataforma = f.id_plataforma
    INNER JOIN gold.dim_tecnologia dtec
        ON dtec.id_tecnologia = f.id_tecnologia
    INNER JOIN gold.dim_comunidad dc
        ON dc.id_comunidad = f.id_comunidad
    WHERE dt.anio BETWEEN 2023 AND 2026
    GROUP BY dt.anio, dt.mes, dt.nombre_mes
)
SELECT
    anio,
    mes,
    nombre_mes,
    total_observaciones,
    total_menciones,
    total_interacciones,
    promedio_score_adopcion,
    score_adopcion_total,
    LAG(score_adopcion_total) OVER (ORDER BY anio, mes) AS score_adopcion_mes_anterior,
    ROUND(
        score_adopcion_total
        - COALESCE(LAG(score_adopcion_total) OVER (ORDER BY anio, mes), 0),
        4
    ) AS variacion_absoluta_adopcion,
    ROUND(
        (
            score_adopcion_total
            - LAG(score_adopcion_total) OVER (ORDER BY anio, mes)
        ) * 100.0 / NULLIF(LAG(score_adopcion_total) OVER (ORDER BY anio, mes), 0),
        2
    ) AS variacion_porcentual_adopcion
FROM adopcion_mensual
ORDER BY anio, mes;
-- Guia de interpretacion:
-- Meses con variacion positiva muestran crecimiento en adopcion frente
-- al mes anterior. La serie permite identificar aceleraciones,
-- estancamientos o caidas en el periodo 2023-2026.


-- ==========================================================
-- PREGUNTA SECUNDARIA 5:
-- Que plataformas o comunidades impulsan mas la conversacion tecnica
-- sobre agentes de IA?
-- Consulta con ranking por plataforma/comunidad.
-- ==========================================================
SELECT
    dp.nombre_plataforma,
    dp.tipo_plataforma,
    dc.nombre_comunidad,
    dc.tipo_comunidad,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(SUM(f.score_comunidad), 4) AS score_comunidad_total,
    ROUND(SUM(f.score_actividad), 4) AS score_actividad_total,
    DENSE_RANK() OVER (
        ORDER BY SUM(f.score_comunidad) DESC, SUM(f.score_actividad) DESC
    ) AS ranking_comunidad
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
INNER JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad
WHERE dt.anio BETWEEN 2023 AND 2026
GROUP BY
    dp.nombre_plataforma,
    dp.tipo_plataforma,
    dc.nombre_comunidad,
    dc.tipo_comunidad
ORDER BY ranking_comunidad, score_comunidad_total DESC, total_observaciones DESC;
-- Guia de interpretacion:
-- Las plataformas o comunidades con mayor ranking concentran la
-- conversacion tecnica. Esto permite identificar donde se producen mas
-- menciones, interacciones o discusiones sobre agentes de IA.


-- ==========================================================
-- PREGUNTA SECUNDARIA 6:
-- Que tecnologias o categorias se asocian con mayor frecuencia al uso
-- de agentes de IA?
-- Consulta de distribucion por categoria tecnologica.
-- ==========================================================
SELECT
    dtec.nombre_tecnologia,
    dtec.categoria_tecnologia,
    dtec.dominio_tecnologico,
    dtec.tipo_senal,
    COUNT(*) AS total_observaciones,
    COUNT(DISTINCT da.id_agente) AS agentes_distintos,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(AVG(f.score_adopcion), 4) AS promedio_score_adopcion,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_participacion_categoria
FROM gold.fact_actividad_agente_ia f
INNER JOIN gold.dim_tiempo dt
    ON dt.id_tiempo = f.id_tiempo
INNER JOIN gold.dim_agente da
    ON da.id_agente = f.id_agente
INNER JOIN gold.dim_fuente df
    ON df.id_fuente = f.id_fuente
INNER JOIN gold.dim_plataforma dp
    ON dp.id_plataforma = f.id_plataforma
INNER JOIN gold.dim_tecnologia dtec
    ON dtec.id_tecnologia = f.id_tecnologia
INNER JOIN gold.dim_comunidad dc
    ON dc.id_comunidad = f.id_comunidad
WHERE dt.anio BETWEEN 2023 AND 2026
GROUP BY
    dtec.nombre_tecnologia,
    dtec.categoria_tecnologia,
    dtec.dominio_tecnologico,
    dtec.tipo_senal
ORDER BY total_observaciones DESC, porcentaje_participacion_categoria DESC;
-- Guia de interpretacion:
-- Las categorias con mayor participacion indican los contextos tecnicos
-- mas asociados al uso o mencion de agentes de IA dentro del Data
-- Warehouse.
