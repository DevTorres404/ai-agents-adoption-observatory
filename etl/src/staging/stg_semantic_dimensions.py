"""Enriquecimiento determinista para las dimensiones semánticas de Gold.

La capa no inventa contexto: primero usa metadatos estructurados de Raw,
después aplica un vocabulario explícito sobre título/texto y, si no existe
evidencia suficiente, conserva el miembro ``No determinada``.
"""

import pandas as pd

from src.utils.logger import global_logger


# Plataforma significa entorno de ejecución o integración del agente, no canal
# de extracción. Ninguna regla utiliza ``fuente`` ni la columna heredada
# ``plataforma``; sin evidencia se conserva ``No determinada``.
PLATFORM_RULES = [
    ("VS Code", "Entorno de desarrollo", "Ecosistema Microsoft", r"vs[ -]?code|visual studio code"),
    ("JetBrains IDEs", "Entorno de desarrollo", "Ecosistema JetBrains", r"\bjetbrains\b|\bintellij\b|\bpycharm\b"),
    ("Terminal / CLI", "Interfaz de línea de comandos", "Desarrollo local", r"command[ -]?line|\bcli\b|\bterminal\b"),
    ("GitHub", "Plataforma DevOps", "Ecosistema GitHub", r"github actions|github app|pull request"),
    ("Amazon Web Services", "Plataforma cloud", "Cloud", r"amazon web services|aws (?:lambda|bedrock|cloud|codebuild|sagemaker)"),
    ("Microsoft Azure", "Plataforma cloud", "Cloud", r"microsoft azure|\bazure\b"),
    ("Google Cloud", "Plataforma cloud", "Cloud", r"google cloud|\bgcp\b"),
    ("API / SDK", "Interfaz programática", "Integración de software", r"\bapi\b|\bsdk\b"),
    ("Web", "Aplicación web", "Navegador", r"web[ -]?app|web[ -]?based|browser extension|interfaz web"),
    ("Extensión de IDE", "Integración de editor", "Herramientas de desarrollo", r"ide extension|editor extension|ide plugin|editor plugin"),
]


# Solo se usan productos cuyo formato de ejecución está definido por su propia
# identidad. Las plataformas multipropósito (p. ej. Codex o Copilot) requieren
# evidencia contextual y no se fuerzan mediante esta tabla.
AGENT_PLATFORM_RULES = {
    "cursor": ("IDE dedicado", "Entorno de desarrollo", "Desarrollo local"),
    "windsurf": ("IDE dedicado", "Entorno de desarrollo", "Desarrollo local"),
    "aws kiro": ("IDE dedicado", "Entorno de desarrollo", "Ecosistema AWS"),
    "claude code": ("Terminal / CLI", "Interfaz de línea de comandos", "Desarrollo local"),
    "aider": ("Terminal / CLI", "Interfaz de línea de comandos", "Desarrollo local"),
    "gemini cli": ("Terminal / CLI", "Interfaz de línea de comandos", "Desarrollo local"),
    "jetbrains junie": ("JetBrains IDEs", "Entorno de desarrollo", "Ecosistema JetBrains"),
    "cline": ("VS Code", "Entorno de desarrollo", "Ecosistema Microsoft"),
    "roo code": ("VS Code", "Entorno de desarrollo", "Ecosistema Microsoft"),
}


SOURCE_COMMUNITY_RULES = {
    "devto": ("DEV Community", "comunidad técnica"),
    "hackernews": ("Hacker News", "foro técnico"),
    "google_trends": ("Audiencia de Google Search", "audiencia de búsqueda"),
    "fuente_propia": ("Comunidad UPSE", "comunidad académica"),
    "stackoverflow": ("Stack Overflow", "Q&A técnica"),
    "arxiv": ("arXiv", "repositorio académico"),
    "gnews": ("Google News", "agregador editorial"),
}


SOURCE_SIGNAL_RULES = {
    "github": "Actividad de repositorio",
    "catalogo": "Actividad de desarrollo",
    "devto": "Publicación técnica",
    "hackernews": "Discusión técnica",
    "google_trends": "Interés de búsqueda",
    "fuente_propia": "Adopción declarada",
    "reddit": "Discusión comunitaria",
    "stackoverflow": "Pregunta o respuesta técnica",
    "arxiv": "Publicación científica",
    "gnews": "Cobertura mediática",
}


# nombre, categoría, dominio y patrón verificable. El orden resuelve
# coincidencias específicas antes de términos más generales.
TECHNOLOGY_RULES = [
    ("TypeScript", "Lenguaje de programación", "Desarrollo de software", r"\btypescript\b"),
    ("JavaScript", "Lenguaje de programación", "Desarrollo de software", r"\bjavascript\b|\bjs\b"),
    ("Python", "Lenguaje de programación", "Desarrollo de software", r"\bpython\b"),
    ("C# / .NET", "Plataforma de desarrollo", "Desarrollo de software", r"c#|\bcsharp\b|\.net\b|\bdotnet\b"),
    ("C++", "Lenguaje de programación", "Desarrollo de software", r"c\+\+|\bcpp\b"),
    ("Java", "Lenguaje de programación", "Desarrollo de software", r"\bjava\b"),
    ("Rust", "Lenguaje de programación", "Desarrollo de software", r"\brust\b"),
    ("Golang", "Lenguaje de programación", "Desarrollo de software", r"\bgolang\b"),
    ("PHP", "Lenguaje de programación", "Desarrollo de software", r"\bphp\b"),
    ("Ruby", "Lenguaje de programación", "Desarrollo de software", r"\bruby\b"),
    ("Kotlin", "Lenguaje de programación", "Desarrollo de software", r"\bkotlin\b"),
    ("Swift", "Lenguaje de programación", "Desarrollo de software", r"\bswift\b"),
    ("Scala", "Lenguaje de programación", "Desarrollo de software", r"\bscala\b"),
    ("Dart", "Lenguaje de programación", "Desarrollo de software", r"\bdart\b"),
    ("Shell", "Lenguaje de programación", "Desarrollo de software", r"\bshell\b|\bbash\b|\bpowershell\b"),
    ("R", "Lenguaje de programación", "Ciencia de datos", r"(?:^|[,;|\s])r(?:$|[,;|\s])"),
    ("SQL", "Lenguaje de consulta", "Datos y analítica", r"\bsql\b|postgresql|sql server|mysql"),
    ("React", "Framework o librería", "Aplicaciones web", r"\breact(?:js)?\b"),
    ("Angular", "Framework o librería", "Aplicaciones web", r"\bangular\b"),
    ("Vue.js", "Framework o librería", "Aplicaciones web", r"\bvue(?:\.js|js)?\b"),
    ("Spring Boot", "Framework o librería", "Aplicaciones backend", r"\bspring[ -]?boot\b"),
    ("Node.js", "Runtime", "Aplicaciones backend", r"\bnode(?:\.js|js)\b"),
    ("Docker", "Infraestructura", "DevOps y plataforma", r"\bdocker\b|containerization"),
    ("Kubernetes", "Infraestructura", "DevOps y plataforma", r"\bkubernetes\b|\bk8s\b"),
    ("Microsoft Azure", "Plataforma cloud", "Cloud", r"\bazure\b"),
    ("Amazon Web Services", "Plataforma cloud", "Cloud", r"\baws\b|amazon web services"),
    ("Google Cloud", "Plataforma cloud", "Cloud", r"google cloud|\bgcp\b"),
    ("VS Code", "Entorno de desarrollo", "Herramientas de desarrollo", r"vs[ -]?code|visual studio code"),
    ("JetBrains IDEs", "Entorno de desarrollo", "Herramientas de desarrollo", r"\bjetbrains\b|intellij|pycharm"),
    ("Model Context Protocol", "Protocolo de IA", "IA generativa y agentes", r"model context protocol|\bmcp\b"),
    ("RAG", "Arquitectura de IA", "IA generativa y agentes", r"retrieval[ -]augmented|\brag\b"),
    ("Modelos de lenguaje", "Tecnología de IA", "IA generativa y agentes", r"large language model|\bllms?\b"),
    ("API / SDK", "Interfaz de integración", "Integración de software", r"\bapi\b|\bsdk\b"),
    ("CLI", "Interfaz de integración", "Herramientas de desarrollo", r"command[ -]line|\bcli\b"),
    ("Testing", "Capacidad de ingeniería", "Ingeniería de software asistida", r"\btesting\b|\btests?\b"),
    ("Depuración", "Capacidad de ingeniería", "Ingeniería de software asistida", r"debugging|depuración"),
    ("Revisión de código", "Capacidad de ingeniería", "Ingeniería de software asistida", r"code review|revisión de código"),
    ("Inteligencia artificial", "Área de investigación", "IA y aprendizaje automático", r"artificial-intelligence|\bcs\.ai\b"),
    ("Aprendizaje automático", "Área de investigación", "IA y aprendizaje automático", r"machinelearning|machine learning|\bcs\.lg\b"),
    ("Procesamiento de lenguaje natural", "Área de investigación", "IA y aprendizaje automático", r"natural language processing|\bcs\.cl\b"),
    ("Ingeniería de software", "Área de investigación", "Desarrollo de software", r"software engineering|\bcs\.se\b"),
]


def _text_series(df, column):
    if column not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="string")
    return (
        df[column]
        .fillna("")
        .astype(str)
        .replace({"nan": "", "None": "", "<NA>": ""})
        .str.strip()
    )


def enrich_semantic_dimensions(df):
    """Añade claves de negocio explícitas para plataforma, tecnología y comunidad."""
    result = df.copy()
    source = _text_series(result, "fuente").str.lower()

    structured_technology = _text_series(result, "tecnologia_raw")
    structured_platform_context = (
        structured_technology + " | "
        + _text_series(result, "llm_entorno_uso") + " | "
        + _text_series(result, "llm_tipo_integracion")
    )
    platform_context = (
        structured_platform_context + " | "
        + _text_series(result, "titulo") + " | "
        + _text_series(result, "texto") + " | "
        + _text_series(result, "llm_capacidades")
    )
    agent_name = _text_series(result, "nombre_agente").str.lower()

    result["dim_nombre_plataforma"] = "No determinada"
    result["dim_tipo_plataforma"] = "No determinado"
    result["dim_ecosistema"] = "No determinado"
    result["dim_plataforma_metodo"] = "sin_evidencia"

    for name, platform_type, ecosystem, pattern in PLATFORM_RULES:
        unresolved = result["dim_nombre_plataforma"].eq("No determinada")
        matches = unresolved & structured_platform_context.str.contains(pattern, case=False, regex=True, na=False)
        result.loc[matches, ["dim_nombre_plataforma", "dim_tipo_plataforma", "dim_ecosistema", "dim_plataforma_metodo"]] = [
            name, platform_type, ecosystem, "metadata_estructurada"
        ]

    for name, platform_type, ecosystem, pattern in PLATFORM_RULES:
        unresolved = result["dim_nombre_plataforma"].eq("No determinada")
        matches = unresolved & platform_context.str.contains(pattern, case=False, regex=True, na=False)
        result.loc[matches, ["dim_nombre_plataforma", "dim_tipo_plataforma", "dim_ecosistema", "dim_plataforma_metodo"]] = [
            name, platform_type, ecosystem, "regla_contextual"
        ]

    for agent, (name, platform_type, ecosystem) in AGENT_PLATFORM_RULES.items():
        unresolved = result["dim_nombre_plataforma"].eq("No determinada")
        matches = unresolved & agent_name.eq(agent)
        result.loc[matches, ["dim_nombre_plataforma", "dim_tipo_plataforma", "dim_ecosistema", "dim_plataforma_metodo"]] = [
            name, platform_type, ecosystem, "regla_agente"
        ]

    # El contrato histórico exige la columna ``plataforma``. Una vez inferida
    # la dimensión real, se sincroniza para que Staging tampoco conserve el
    # antiguo espejo de ``fuente``.
    result["plataforma"] = result["dim_nombre_plataforma"]

    context = (
        structured_technology + " | "
        + _text_series(result, "titulo") + " | "
        + _text_series(result, "texto") + " | "
        + _text_series(result, "llm_capacidades")
    )

    result["dim_nombre_tecnologia"] = "No determinada"
    result["dim_categoria_tecnologia"] = "No determinada"
    result["dim_dominio_tecnologico"] = "No determinado"
    result["dim_tecnologia_metodo"] = "sin_evidencia"

    for name, category, domain, pattern in TECHNOLOGY_RULES:
        unresolved = result["dim_nombre_tecnologia"].eq("No determinada")
        matches = unresolved & structured_technology.str.contains(pattern, case=False, regex=True, na=False)
        result.loc[matches, ["dim_nombre_tecnologia", "dim_categoria_tecnologia", "dim_dominio_tecnologico", "dim_tecnologia_metodo"]] = [
            name, category, domain, "metadata_estructurada"
        ]

    for name, category, domain, pattern in TECHNOLOGY_RULES:
        unresolved = result["dim_nombre_tecnologia"].eq("No determinada")
        matches = unresolved & context.str.contains(pattern, case=False, regex=True, na=False)
        result.loc[matches, ["dim_nombre_tecnologia", "dim_categoria_tecnologia", "dim_dominio_tecnologico", "dim_tecnologia_metodo"]] = [
            name, category, domain, "regla_contextual"
        ]

    result["dim_tipo_senal"] = source.map(SOURCE_SIGNAL_RULES).fillna("Observación digital")

    community_name = source.map({key: value[0] for key, value in SOURCE_COMMUNITY_RULES.items()})
    community_type = source.map({key: value[1] for key, value in SOURCE_COMMUNITY_RULES.items()})
    raw_community = _text_series(result, "comunidad_raw")
    raw_community_type = _text_series(result, "tipo_comunidad_raw")
    raw_region = _text_series(result, "region_comunidad_raw")

    has_raw_community = raw_community.ne("")
    has_raw_type = raw_community_type.ne("")
    result["dim_nombre_comunidad"] = community_name.fillna("Comunidad no determinada")
    result.loc[has_raw_community, "dim_nombre_comunidad"] = raw_community[has_raw_community]
    result["dim_tipo_comunidad"] = community_type.fillna("comunidad no determinada")
    result.loc[has_raw_type, "dim_tipo_comunidad"] = raw_community_type[has_raw_type]
    result["dim_region_comunidad"] = "Global"
    result.loc[raw_region.ne(""), "dim_region_comunidad"] = raw_region[raw_region.ne("")]
    result["dim_comunidad_metodo"] = has_raw_community.map({True: "metadata_estructurada", False: "regla_fuente"})

    varchar_limits = {
        "dim_nombre_plataforma": 100,
        "dim_tipo_plataforma": 100,
        "dim_ecosistema": 100,
        "dim_nombre_tecnologia": 120,
        "dim_categoria_tecnologia": 100,
        "dim_dominio_tecnologico": 120,
        "dim_tipo_senal": 100,
        "dim_nombre_comunidad": 120,
        "dim_tipo_comunidad": 100,
        "dim_region_comunidad": 100,
    }
    for column, limit in varchar_limits.items():
        result[column] = result[column].astype(str).str.slice(0, limit)

    platform_coverage = result["dim_nombre_plataforma"].ne("No determinada").mean() * 100 if len(result) else 0
    technology_coverage = result["dim_nombre_tecnologia"].ne("No determinada").mean() * 100 if len(result) else 0
    metadata_coverage = result["dim_tecnologia_metodo"].eq("metadata_estructurada").mean() * 100 if len(result) else 0
    global_logger.info(
        "Dimensiones semánticas enriquecidas: plataforma con evidencia %.2f%%; tecnología con evidencia %.2f%% (metadata estructurada %.2f%%).",
        platform_coverage,
        technology_coverage,
        metadata_coverage,
    )
    return result
