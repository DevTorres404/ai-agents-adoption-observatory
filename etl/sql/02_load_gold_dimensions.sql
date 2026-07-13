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
    caracteristica_clave,
    modelo_precios,
    es_agente_identificado
)
SELECT
    nombre_agente,
    CASE nombre_agente
        WHEN 'Cursor' THEN 'Usuarios de VS Code, desarrollo general'
        WHEN 'Claude Code' THEN 'Tareas de razonamiento complejo'
        WHEN 'Codex' THEN 'Modelo fundacional de codigo'
        WHEN 'GitHub Copilot' THEN 'Equipos GitHub/Microsoft'
        WHEN 'Cline' THEN 'Usuarios de VS Code agnosticos al modelo'
        WHEN 'Roo Code' THEN 'Power users, personalizacion'
        WHEN 'Windsurf' THEN 'Codebases grandes, enterprise'
        WHEN 'Aider' THEN 'Desarrolladores terminal-first'
        WHEN 'Augment' THEN 'Enterprise Code AI'
        WHEN 'JetBrains Junie' THEN 'Ecosistema JetBrains'
        WHEN 'Gemini CLI' THEN 'Desarrollo en Google Cloud'
        WHEN 'AWS Kiro' THEN 'Equipos nativos de AWS'
        WHEN 'Kilo Code' THEN 'Desarrollo Web / iOS'
        WHEN 'Zencoder' THEN 'AI Code Analysis'
        ELSE 'No especificado'
    END AS categoria_agente,
    CASE nombre_agente
        WHEN 'Cursor' THEN 'IDE dedicado'
        WHEN 'Claude Code' THEN 'Primero en terminal'
        WHEN 'Codex' THEN 'API / Modelo'
        WHEN 'GitHub Copilot' THEN 'Ecosistema nativo'
        WHEN 'Cline' THEN 'Extension BYOK'
        WHEN 'Roo Code' THEN 'Extension BYOK'
        WHEN 'Windsurf' THEN 'IDE dedicado'
        WHEN 'Aider' THEN 'Primero en terminal'
        WHEN 'Augment' THEN 'Extension IDE'
        WHEN 'JetBrains Junie' THEN 'Ecosistema nativo'
        WHEN 'Gemini CLI' THEN 'CLI y Extension'
        WHEN 'AWS Kiro' THEN 'IDE dedicado'
        WHEN 'Kilo Code' THEN 'IDE dedicado'
        WHEN 'Zencoder' THEN 'CLI / Integracion'
        ELSE 'No especificado'
    END AS tipo_agente,
    CASE nombre_agente
        WHEN 'Claude Code' THEN 'Anthropic'
        WHEN 'Codex' THEN 'OpenAI'
        WHEN 'GitHub Copilot' THEN 'Microsoft / GitHub'
        WHEN 'Augment' THEN 'Augment Inc.'
        WHEN 'JetBrains Junie' THEN 'JetBrains'
        WHEN 'Gemini CLI' THEN 'Google'
        WHEN 'AWS Kiro' THEN 'Amazon Web Services'
        WHEN 'Zencoder' THEN 'Zencoder'
        ELSE 'No especificado'
    END AS proveedor,
    CASE nombre_agente
        WHEN 'Cursor' THEN 'Razonamiento en codebase multi-repo'
        WHEN 'Claude Code' THEN 'Profundidad de razonamiento multi-paso'
        WHEN 'Codex' THEN 'Pionero en autocompletado LLM'
        WHEN 'GitHub Copilot' THEN 'Copilot Workspaces, integracion profunda con GitHub'
        WHEN 'Cline' THEN 'Open source, agnostico al modelo'
        WHEN 'Roo Code' THEN 'Sistema multi-persona de agentes'
        WHEN 'Windsurf' THEN 'Carga automatica de contexto (Cascade)'
        WHEN 'Aider' THEN 'Agnostico al editor, Git nativo'
        WHEN 'Augment' THEN 'Context awareness ultra rapido'
        WHEN 'JetBrains Junie' THEN 'Integracion nativa con JetBrains'
        WHEN 'Gemini CLI' THEN 'Integracion nativa con GCP'
        WHEN 'AWS Kiro' THEN 'Flujo basado en specs y hooks'
        WHEN 'Kilo Code' THEN 'Agente nativo veloz'
        WHEN 'Zencoder' THEN 'Analisis de vulnerabilidades'
        ELSE 'No especificado'
    END AS caracteristica_clave,
    CASE nombre_agente
        WHEN 'Cursor' THEN 'Gratis + de pago'
        WHEN 'Claude Code' THEN 'Segun uso'
        WHEN 'Codex' THEN 'Deprecado / API'
        WHEN 'GitHub Copilot' THEN 'Suscripcion por usuario'
        WHEN 'Cline' THEN 'Gratis (BYOK)'
        WHEN 'Roo Code' THEN 'Gratis (BYOK)'
        WHEN 'Windsurf' THEN 'Gratis + de pago'
        WHEN 'Aider' THEN 'Gratis (BYOK)'
        WHEN 'Augment' THEN 'Enterprise'
        WHEN 'JetBrains Junie' THEN 'Suscripcion JetBrains'
        WHEN 'Gemini CLI' THEN 'Suscripcion / Enterprise'
        WHEN 'AWS Kiro' THEN 'Preview (gratis)'
        WHEN 'Kilo Code' THEN 'Suscripcion'
        WHEN 'Zencoder' THEN 'Suscripcion'
        ELSE 'No especificado'
    END AS modelo_precios,
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
WITH fuentes_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') AS nombre_fuente,
        COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_fuente,
        (COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') = 'fuente_propia') AS es_fuente_propia
    FROM staging.stg_actividad_agente_ia s
    WHERE s.fuente IS NOT NULL
)
INSERT INTO gold.dim_fuente (
    nombre_fuente,
    tipo_fuente,
    categoria_fuente,
    confiabilidad_fuente,
    es_fuente_propia
)
SELECT
    nombre_fuente,
    MIN(tipo_fuente) AS tipo_fuente,
    MIN(tipo_fuente) AS categoria_fuente,
    'No especificado' AS confiabilidad_fuente,
    BOOL_OR(es_fuente_propia) AS es_fuente_propia
FROM fuentes_distintas
GROUP BY nombre_fuente;


-- ==========================================================
-- 04. DIMENSION PLATAFORMA
-- Fuente: plataforma y tipo_fuente desde Staging.
-- ==========================================================
WITH plataformas_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS nombre_plataforma,
        COALESCE(NULLIF(BTRIM(s.llm_tipo_integracion), ''), NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_plataforma,
        COALESCE(NULLIF(BTRIM(s.llm_entorno_uso), ''), NULLIF(BTRIM(s.fuente), ''), 'No especificado') AS ecosistema
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
        COALESCE(NULLIF(BTRIM(s.llm_categoria_tecnologia), ''), NULLIF(BTRIM(s.categoria), ''), 'No especificado') AS categoria_tecnologia,
        COALESCE(NULLIF(BTRIM(s.llm_capacidades), ''), NULLIF(BTRIM(s.plataforma), ''), 'No especificado') AS dominio_tecnologico,
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
        COALESCE(NULLIF(BTRIM(s.llm_comunidad_tipo), ''), NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_comunidad,
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


