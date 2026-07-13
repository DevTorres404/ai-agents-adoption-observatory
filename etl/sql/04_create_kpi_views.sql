-- ==========================================================
-- ENTREGABLE 4 - VISTAS ANALITICAS KPI GOLD
-- Motor: PostgreSQL
--
-- Restriccion academica:
-- Las vistas consultan exclusivamente tablas del esquema gold.
-- No consultan Staging, Raw ni datos simulados.
-- ==========================================================

DROP VIEW IF EXISTS gold.vw_kpi_distribucion_por_plataforma;
DROP VIEW IF EXISTS gold.vw_kpi_crecimiento_mensual;
DROP VIEW IF EXISTS gold.vw_kpi_popularidad_open_source;
DROP VIEW IF EXISTS gold.vw_kpi_ranking_agentes;
DROP VIEW IF EXISTS gold.vw_kpi_tendencia_mensual;
DROP VIEW IF EXISTS gold.vw_kpi_participacion_por_fuente;
DROP VIEW IF EXISTS gold.vw_kpi_adopcion_por_agente;


-- ==========================================================
-- 01. KPI: Adopcion por agente
-- Objetivo:
-- Medir el nivel agregado de adopcion observado para cada agente de IA.
-- Formula:
-- AVG(score_adopcion), SUM(cantidad_menciones), SUM(cantidad_interacciones)
-- agrupado por agente.
-- Interpretacion esperada:
-- Un mayor promedio de adopcion e interacciones indica mayor presencia
-- o uso relativo del agente dentro del ecosistema observado.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_adopcion_por_agente AS
SELECT
    da.nombre_agente,
    da.categoria_agente,
    COUNT(*) AS total_observaciones,
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
GROUP BY da.nombre_agente, da.categoria_agente;


-- ==========================================================
-- 02. KPI: Participacion por fuente
-- Objetivo:
-- Identificar el peso relativo de cada fuente dentro del Data Warehouse.
-- Formula:
-- COUNT(*) por fuente / COUNT(*) total de hechos * 100.
-- Interpretacion esperada:
-- El porcentaje permite verificar que fuentes dominan el analisis y si
-- existe dependencia excesiva de un solo origen.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_participacion_por_fuente AS
SELECT
    df.nombre_fuente,
    df.tipo_fuente,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_participacion
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
GROUP BY df.nombre_fuente, df.tipo_fuente;


-- ==========================================================
-- 03. KPI: Tendencia mensual
-- Objetivo:
-- Analizar la evolucion mensual de menciones, interacciones y actividad.
-- Formula:
-- SUM(metricas) y AVG(scores) agrupados por anio y mes.
-- Interpretacion esperada:
-- Permite observar meses con mayor intensidad de adopcion o actividad
-- relacionada con agentes de IA.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_tendencia_mensual AS
SELECT
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(SUM(f.score_actividad), 4) AS score_actividad_total,
    ROUND(AVG(f.score_popularidad), 4) AS promedio_popularidad,
    ROUND(AVG(f.score_adopcion), 4) AS promedio_adopcion
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
GROUP BY dt.anio, dt.mes, dt.nombre_mes;


-- ==========================================================
-- 04. KPI: Ranking de agentes
-- Objetivo:
-- Ordenar los agentes de IA segun su relevancia analitica total.
-- Formula:
-- SUM(score_actividad + score_popularidad + score_adopcion +
-- score_comunidad + score_innovacion) y RANK() descendente.
-- Interpretacion esperada:
-- Los primeros lugares representan agentes con mayor senal agregada
-- dentro de las fuentes observadas.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_ranking_agentes AS
SELECT
    da.nombre_agente,
    COUNT(*) AS total_observaciones,
    ROUND(SUM(
        f.score_actividad
        + f.score_popularidad
        + f.score_adopcion
        + f.score_comunidad
        + f.score_innovacion
    ), 4) AS score_total_relevancia,
    RANK() OVER (
        ORDER BY SUM(
            f.score_actividad
            + f.score_popularidad
            + f.score_adopcion
            + f.score_comunidad
            + f.score_innovacion
        ) DESC
    ) AS ranking_agente,
    DENSE_RANK() OVER (
        ORDER BY COUNT(*) DESC
    ) AS ranking_por_observaciones
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
GROUP BY da.nombre_agente;


-- ==========================================================
-- 05. KPI: Popularidad open source
-- Objetivo:
-- Medir popularidad tecnica en fuentes abiertas, especialmente GitHub
-- y datasets de actividad tecnica.
-- Formula:
-- SUM(stars_github), SUM(forks_github), SUM(issues_abiertos),
-- SUM(releases) y AVG(score_popularidad) por agente.
-- Interpretacion esperada:
-- Un agente con mayor actividad open source muestra mayor presencia
-- tecnica en repositorios y artefactos de desarrollo.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_popularidad_open_source AS
SELECT
    da.nombre_agente,
    df.nombre_fuente,
    dp.nombre_plataforma,
    COUNT(*) AS total_observaciones,
    SUM(f.stars_github) AS total_stars,
    SUM(f.forks_github) AS total_forks,
    SUM(f.issues_abiertos) AS total_issues_abiertos,
    SUM(f.releases) AS total_releases,
    ROUND(AVG(f.score_popularidad), 4) AS promedio_score_popularidad,
    ROUND(SUM(f.score_actividad), 4) AS score_actividad_total
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
WHERE df.nombre_fuente IN ('github', 'api', 'catalogo')
   OR dp.nombre_plataforma IN ('github', 'api', 'aidedev_ai_coding')
GROUP BY da.nombre_agente, df.nombre_fuente, dp.nombre_plataforma;


-- ==========================================================
-- 06. KPI: Crecimiento mensual
-- Objetivo:
-- Comparar el volumen mensual actual contra el mes anterior.
-- Formula:
-- COUNT(*) mensual, LAG(COUNT(*)) y variacion porcentual mensual.
-- Interpretacion esperada:
-- Un crecimiento positivo indica aumento de observaciones o menciones
-- sobre agentes de IA frente al periodo mensual previo.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_crecimiento_mensual AS
WITH mensual AS (
    SELECT
        dt.anio,
        dt.mes,
        dt.nombre_mes,
        COUNT(*) AS total_observaciones,
        SUM(f.cantidad_menciones) AS total_menciones,
        SUM(f.cantidad_interacciones) AS total_interacciones,
        ROUND(SUM(f.score_actividad), 4) AS score_actividad_total
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
    GROUP BY dt.anio, dt.mes, dt.nombre_mes
)
SELECT
    anio,
    mes,
    nombre_mes,
    total_observaciones,
    LAG(total_observaciones) OVER (ORDER BY anio, mes) AS observaciones_mes_anterior,
    total_observaciones
        - COALESCE(LAG(total_observaciones) OVER (ORDER BY anio, mes), 0) AS variacion_absoluta,
    ROUND(
        (
            total_observaciones
            - LAG(total_observaciones) OVER (ORDER BY anio, mes)
        ) * 100.0 / NULLIF(LAG(total_observaciones) OVER (ORDER BY anio, mes), 0),
        2
    ) AS variacion_porcentual,
    total_menciones,
    total_interacciones,
    score_actividad_total
FROM mensual;


-- ==========================================================
-- 07. KPI: Distribucion por plataforma
-- Objetivo:
-- Analizar la concentracion de registros por plataforma de observacion.
-- Formula:
-- COUNT(*) por plataforma / COUNT(*) total * 100, junto con SUM de
-- menciones e interacciones.
-- Interpretacion esperada:
-- Muestra que plataformas aportan mas senales al DW y donde se concentra
-- la evidencia analitica.
-- ==========================================================
CREATE OR REPLACE VIEW gold.vw_kpi_distribucion_por_plataforma AS
SELECT
    dp.nombre_plataforma,
    dp.tipo_plataforma,
    dp.ecosistema,
    COUNT(*) AS total_observaciones,
    SUM(f.cantidad_menciones) AS total_menciones,
    SUM(f.cantidad_interacciones) AS total_interacciones,
    ROUND(AVG(f.score_popularidad), 4) AS promedio_popularidad,
    ROUND(
        COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS porcentaje_distribucion,
    DENSE_RANK() OVER (
        ORDER BY COUNT(*) DESC
    ) AS ranking_plataforma
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
GROUP BY dp.nombre_plataforma, dp.tipo_plataforma, dp.ecosistema;


