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

-- El camino normal es incremental: cada dimensión conserva su surrogate key
-- y actualiza atributos por su clave natural. La ausencia no elimina filas.


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
FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
WHERE s.fecha_evento IS NOT NULL
ON CONFLICT (fecha) DO UPDATE SET
    anio = EXCLUDED.anio,
    semestre = EXCLUDED.semestre,
    trimestre = EXCLUDED.trimestre,
    mes = EXCLUDED.mes,
    nombre_mes = EXCLUDED.nombre_mes,
    semana_anio = EXCLUDED.semana_anio,
    dia_mes = EXCLUDED.dia_mes,
    dia_semana = EXCLUDED.dia_semana,
    nombre_dia = EXCLUDED.nombre_dia,
    es_fin_semana = EXCLUDED.es_fin_semana;


-- ==========================================================
-- 02. DIMENSION AGENTE
-- Fuente: nombre_agente y categoria desde Staging.
-- proveedor no existe en Staging; se conserva como No especificado.
-- ==========================================================
WITH agentes_distintos AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.nombre_agente), ''), 'No especificado') AS nombre_agente,
        COALESCE(NULLIF(BTRIM(s.categoria), ''), 'No especificado') AS categoria_agente
    FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
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
        WHEN 'Codex' THEN 'Modelo fundacional de codigo'
        WHEN 'GitHub Copilot' THEN 'Equipos GitHub/Microsoft'
        WHEN 'Cursor' THEN 'Usuarios de VS Code, desarrollo general'
        WHEN 'Windsurf' THEN 'Codebases grandes, enterprise'
        WHEN 'Devin' THEN 'Ingenieria de software autonoma'
        WHEN 'OpenCode' THEN 'Desarrollo en terminal agnostico'
        WHEN 'Aider' THEN 'Desarrolladores terminal-first'
        WHEN 'Claude Code' THEN 'Tareas de razonamiento complejo'
        WHEN 'Cline' THEN 'Usuarios de VS Code agnosticos al modelo'
        WHEN 'Antigravity' THEN 'Estado del arte / IDE integrado'
        ELSE 'No especificado'
    END AS categoria_agente,
    CASE nombre_agente
        WHEN 'Codex' THEN 'API / Modelo'
        WHEN 'GitHub Copilot' THEN 'Ecosistema nativo'
        WHEN 'Cursor' THEN 'IDE dedicado'
        WHEN 'Windsurf' THEN 'IDE dedicado'
        WHEN 'Devin' THEN 'Agente autonomo'
        WHEN 'OpenCode' THEN 'Primero en terminal'
        WHEN 'Aider' THEN 'Primero en terminal'
        WHEN 'Claude Code' THEN 'Primero en terminal'
        WHEN 'Cline' THEN 'Extension BYOK'
        WHEN 'Antigravity' THEN 'IDE y Agente'
        ELSE 'No especificado'
    END AS tipo_agente,
    CASE nombre_agente
        WHEN 'Codex' THEN 'OpenAI'
        WHEN 'GitHub Copilot' THEN 'Microsoft / GitHub'
        WHEN 'Cursor' THEN 'Anysphere'
        WHEN 'Windsurf' THEN 'Codeium'
        WHEN 'Devin' THEN 'Cognition'
        WHEN 'OpenCode' THEN 'OpenCode'
        WHEN 'Aider' THEN 'Open Source'
        WHEN 'Claude Code' THEN 'Anthropic'
        WHEN 'Cline' THEN 'Open Source'
        WHEN 'Antigravity' THEN 'Google Deepmind'
        ELSE 'No especificado'
    END AS proveedor,
    CASE nombre_agente
        WHEN 'Codex' THEN 'Pionero en autocompletado LLM'
        WHEN 'GitHub Copilot' THEN 'Copilot Workspaces, integracion profunda con GitHub'
        WHEN 'Cursor' THEN 'Razonamiento en codebase multi-repo'
        WHEN 'Windsurf' THEN 'Carga automatica de contexto (Cascade)'
        WHEN 'Devin' THEN 'Agente 100% autonomo cloud'
        WHEN 'OpenCode' THEN 'Orquestador agnostico de terminal'
        WHEN 'Aider' THEN 'Agnostico al editor, Git nativo'
        WHEN 'Claude Code' THEN 'Profundidad de razonamiento multi-paso'
        WHEN 'Cline' THEN 'Open source, agnostico al modelo'
        WHEN 'Antigravity' THEN 'Memoria a largo plazo e integracion total'
        ELSE 'No especificado'
    END AS caracteristica_clave,
    CASE nombre_agente
        WHEN 'Codex' THEN 'Deprecado / API'
        WHEN 'GitHub Copilot' THEN 'Suscripcion por usuario'
        WHEN 'Cursor' THEN 'Gratis + de pago'
        WHEN 'Windsurf' THEN 'Gratis + de pago'
        WHEN 'Devin' THEN 'Enterprise'
        WHEN 'OpenCode' THEN 'Gratis (Open Source)'
        WHEN 'Aider' THEN 'Gratis (BYOK)'
        WHEN 'Claude Code' THEN 'Segun uso'
        WHEN 'Cline' THEN 'Gratis (BYOK)'
        WHEN 'Antigravity' THEN 'Preview / Beta'
        ELSE 'No especificado'
    END AS modelo_precios,
    CASE
        WHEN nombre_agente IN ('Otro Agente IA', 'No especificado')
            THEN FALSE
        ELSE TRUE
    END AS es_agente_identificado
FROM agentes_consolidados
ON CONFLICT (nombre_agente) DO UPDATE SET
    categoria_agente = EXCLUDED.categoria_agente,
    tipo_agente = EXCLUDED.tipo_agente,
    proveedor = EXCLUDED.proveedor,
    caracteristica_clave = EXCLUDED.caracteristica_clave,
    modelo_precios = EXCLUDED.modelo_precios,
    es_agente_identificado = EXCLUDED.es_agente_identificado;


-- ==========================================================
-- 03. DIMENSION FUENTE
-- Fuente: fuente y tipo_fuente desde Staging.
-- confiabilidad_fuente no existe en Staging; se conserva como No especificado.
-- ==========================================================
WITH fuentes_distintas AS (
    SELECT DISTINCT
        COALESCE(NULLIF(BTRIM(s.fuente), ''), 'No especificado') AS nombre_fuente,
        COALESCE(NULLIF(BTRIM(s.tipo_fuente), ''), 'No especificado') AS tipo_fuente
    FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
    WHERE s.fuente IS NOT NULL
)
INSERT INTO gold.dim_fuente (
    nombre_fuente,
    tipo_fuente,
    categoria_fuente,
    confiabilidad_fuente
)
SELECT
    nombre_fuente,
    tipo_fuente,
    tipo_fuente AS categoria_fuente,
    'No especificado' AS confiabilidad_fuente
FROM fuentes_distintas
ON CONFLICT (nombre_fuente, tipo_fuente) DO UPDATE SET
    categoria_fuente = EXCLUDED.categoria_fuente,
    confiabilidad_fuente = EXCLUDED.confiabilidad_fuente;


-- ==========================================================
-- 04. DIMENSION PLATAFORMA
-- Fuente: atributos semánticos explícitos generados en Staging.
-- ==========================================================
WITH plataformas_consolidadas AS (
    SELECT DISTINCT ON (
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada')
    )
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada') AS nombre_plataforma,
        COALESCE(NULLIF(BTRIM(s.dim_tipo_plataforma), ''), 'No determinado') AS tipo_plataforma,
        COALESCE(NULLIF(BTRIM(s.dim_ecosistema), ''), 'No determinado') AS ecosistema
    FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
    WHERE s.dim_nombre_plataforma IS NOT NULL
    ORDER BY
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada'),
        s.fecha_evento DESC NULLS LAST,
        s.raw_file_id DESC NULLS LAST,
        s.raw_record_id DESC NULLS LAST
)
INSERT INTO gold.dim_plataforma (
    nombre_plataforma,
    tipo_plataforma,
    ecosistema
)
SELECT
    nombre_plataforma,
    tipo_plataforma,
    ecosistema
FROM plataformas_consolidadas
ON CONFLICT (nombre_plataforma) DO UPDATE SET
    tipo_plataforma = EXCLUDED.tipo_plataforma,
    ecosistema = EXCLUDED.ecosistema;


-- ==========================================================
-- 05. DIMENSION TECNOLOGIA
-- Fuente: metadata estructurada o vocabulario contextual trazable de Staging.
-- ==========================================================
WITH tecnologias_consolidadas AS (
    SELECT DISTINCT ON (
        COALESCE(NULLIF(BTRIM(s.dim_nombre_tecnologia), ''), 'No determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_categoria_tecnologia), ''), 'No determinada')
    )
        COALESCE(NULLIF(BTRIM(s.dim_nombre_tecnologia), ''), 'No determinada') AS nombre_tecnologia,
        COALESCE(NULLIF(BTRIM(s.dim_categoria_tecnologia), ''), 'No determinada') AS categoria_tecnologia,
        COALESCE(NULLIF(BTRIM(s.dim_dominio_tecnologico), ''), 'No determinado') AS dominio_tecnologico,
        COALESCE(NULLIF(BTRIM(s.dim_tipo_senal), ''), 'Observación digital') AS tipo_senal
    FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
    WHERE s.dim_nombre_tecnologia IS NOT NULL
    ORDER BY
        COALESCE(NULLIF(BTRIM(s.dim_nombre_tecnologia), ''), 'No determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_categoria_tecnologia), ''), 'No determinada'),
        s.fecha_evento DESC NULLS LAST,
        s.raw_file_id DESC NULLS LAST,
        s.raw_record_id DESC NULLS LAST
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
    dominio_tecnologico,
    tipo_senal
FROM tecnologias_consolidadas
ON CONFLICT (nombre_tecnologia, categoria_tecnologia) DO UPDATE SET
    dominio_tecnologico = EXCLUDED.dominio_tecnologico,
    tipo_senal = EXCLUDED.tipo_senal;


-- ==========================================================
-- 06. DIMENSION COMUNIDAD
-- Fuente: propietario, grupo, foro, institución o medio identificado en Staging.
-- ==========================================================
WITH comunidades_consolidadas AS (
    SELECT DISTINCT ON (
        COALESCE(NULLIF(BTRIM(s.dim_nombre_comunidad), ''), 'Comunidad no determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_tipo_comunidad), ''), 'comunidad no determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada')
    )
        COALESCE(NULLIF(BTRIM(s.dim_nombre_comunidad), ''), 'Comunidad no determinada') AS nombre_comunidad,
        COALESCE(NULLIF(BTRIM(s.dim_tipo_comunidad), ''), 'comunidad no determinada') AS tipo_comunidad,
        COALESCE(NULLIF(BTRIM(s.dim_region_comunidad), ''), 'No especificado') AS region,
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada') AS plataforma_comunidad
    FROM (SELECT * FROM staging.stg_actividad_agente_ia
        WHERE COALESCE(fuente, '') NOT IN ('fuente_propia', 'encuesta')
          AND CASE COALESCE(NULLIF(current_setting('etl.pipeline', true), ''), 'all')
            WHEN 'github' THEN fuente = 'github'
            WHEN 'main' THEN COALESCE(fuente, '') <> 'github'
            WHEN 'all' THEN TRUE
            ELSE FALSE
        END) s
    WHERE s.dim_nombre_comunidad IS NOT NULL
    ORDER BY
        COALESCE(NULLIF(BTRIM(s.dim_nombre_comunidad), ''), 'Comunidad no determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_tipo_comunidad), ''), 'comunidad no determinada'),
        COALESCE(NULLIF(BTRIM(s.dim_nombre_plataforma), ''), 'No determinada'),
        s.fecha_evento DESC NULLS LAST,
        s.raw_file_id DESC NULLS LAST,
        s.raw_record_id DESC NULLS LAST
)
INSERT INTO gold.dim_comunidad (
    nombre_comunidad,
    tipo_comunidad,
    region,
    plataforma_comunidad
)
SELECT
    nombre_comunidad,
    tipo_comunidad,
    region,
    plataforma_comunidad
FROM comunidades_consolidadas
ON CONFLICT (nombre_comunidad, tipo_comunidad, plataforma_comunidad) DO UPDATE SET
    region = EXCLUDED.region;

-- Actualizar estadísticas evita planes de nested-loop costosos al cargar Fact.
ANALYZE gold.dim_tiempo;
ANALYZE gold.dim_agente;
ANALYZE gold.dim_fuente;
ANALYZE gold.dim_plataforma;
ANALYZE gold.dim_tecnologia;
ANALYZE gold.dim_comunidad;
