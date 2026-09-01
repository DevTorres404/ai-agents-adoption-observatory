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
FROM staging.stg_actividad_agente_ia s
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
    tipo_fuente,
    tipo_fuente AS categoria_fuente,
    'No especificado' AS confiabilidad_fuente,
    es_fuente_propia
FROM fuentes_distintas
ON CONFLICT (nombre_fuente, tipo_fuente) DO UPDATE SET
    categoria_fuente = EXCLUDED.categoria_fuente,
    confiabilidad_fuente = EXCLUDED.confiabilidad_fuente,
    es_fuente_propia = EXCLUDED.es_fuente_propia;


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
    FROM staging.stg_actividad_agente_ia s
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
    FROM staging.stg_actividad_agente_ia s
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
    FROM staging.stg_actividad_agente_ia s
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
