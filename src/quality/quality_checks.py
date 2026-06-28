import pandas as pd
from sqlalchemy import text

from src.staging.stg_agents import extract_agent
from src.staging.stg_categories import assign_categories
from src.staging.stg_dates import parse_dates
from src.staging.stg_normalize_columns import normalize_dataframe
from src.utils.db import db_connector


STAGING_CONTRACT_COLUMNS = [
    "id_origen_registro",
    "fuente",
    "tipo_fuente",
    "plataforma",
    "fecha_evento",
    "nombre_agente",
    "categoria",
    "titulo",
    "texto",
    "url",
    "cantidad_menciones",
    "cantidad_interacciones",
    "score_popularidad",
    "stars_github",
    "forks_github",
    "issues_abiertos",
    "releases",
    "indice_adopcion",
    "indice_innovacion",
    "sentimiento_promedio",
    "raw_file_id",
]

DEDUP_KEY = ["fuente", "plataforma", "id_origen_registro", "nombre_agente", "fecha_evento"]
CRITICAL_COLUMNS = ["id_origen_registro", "fuente", "plataforma", "fecha_evento", "nombre_agente", "categoria"]
NUMERIC_COLUMNS = [
    "cantidad_menciones",
    "cantidad_interacciones",
    "score_popularidad",
    "stars_github",
    "forks_github",
    "issues_abiertos",
    "releases",
    "indice_adopcion",
    "indice_innovacion",
    "sentimiento_promedio",
]


def _fetch_raw_rows():
    query = text("""
        SELECT r.raw_data, f.fuente, f.tipo_fuente, f.id AS file_id
        FROM raw.raw_records r
        JOIN raw.raw_files f ON r.file_id = f.id
    """)
    with db_connector.engine.connect() as conn:
        return conn.execute(query).fetchall()


def build_candidate_staging_frame():
    rows = _fetch_raw_rows()
    if not rows:
        return pd.DataFrame(columns=STAGING_CONTRACT_COLUMNS)

    grouped = {}
    for row in rows:
        key = (row.fuente, row.tipo_fuente, row.file_id)
        grouped.setdefault(key, []).append(row.raw_data)

    frames = []
    for (fuente, tipo_fuente, file_id), records in grouped.items():
        raw_df = pd.DataFrame(records)
        meta = {"fuente": fuente, "tipo_fuente": tipo_fuente, "id": file_id}
        frames.append(normalize_dataframe(raw_df, meta))

    df = pd.concat(frames, ignore_index=True)
    df = parse_dates(df)
    df = extract_agent(df)
    df = assign_categories(df)

    for col in DEDUP_KEY:
        if col in df.columns:
            df[col] = df[col].fillna("N/A").astype(str)

    return df


def get_overall_metrics():
    """Obtiene conteos globales sin clasificar toda la merma como duplicidad."""
    metrics = {
        "total_raw_records": 0,
        "total_staging_records": 0,
        "completion_rate": 0.0,
        "total_duplicates_removed": 0,
        "total_nulls_removed": 0,
        "overall_error_rate": 0.0,
    }

    with db_connector.engine.connect() as conn:
        metrics["total_raw_records"] = conn.execute(text("SELECT COUNT(*) FROM raw.raw_records")).scalar() or 0
        metrics["total_staging_records"] = conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia")).scalar() or 0

    if metrics["total_raw_records"] > 0:
        candidate_df = build_candidate_staging_frame()
        duplicate_count = candidate_df.duplicated(subset=DEDUP_KEY, keep="first").sum() if not candidate_df.empty else 0
        metrics["completion_rate"] = round((metrics["total_staging_records"] / metrics["total_raw_records"]) * 100, 2)
        metrics["total_duplicates_removed"] = int(duplicate_count)
        metrics["total_nulls_removed"] = get_critical_null_count()
        metrics["overall_error_rate"] = round(100.0 - metrics["completion_rate"], 2)

    return metrics


def get_nulls_matrix():
    """Analiza nulos por fuente y campo clave en Staging."""
    query = text("""
        SELECT
            fuente,
            COUNT(*) AS total_count,
            SUM(CASE WHEN nombre_agente IS NULL THEN 1 ELSE 0 END) AS null_agente,
            SUM(CASE WHEN fecha_evento IS NULL THEN 1 ELSE 0 END) AS null_fecha,
            SUM(CASE WHEN categoria IS NULL THEN 1 ELSE 0 END) AS null_categoria
        FROM staging.stg_actividad_agente_ia
        GROUP BY fuente
    """)

    matrix = []
    with db_connector.engine.connect() as conn:
        results = conn.execute(query).fetchall()
        for row in results:
            for field in ["agente", "fecha", "categoria"]:
                null_count = getattr(row, f"null_{field}")
                total = row.total_count
                matrix.append({
                    "source": row.fuente,
                    "column_name": "nombre_agente" if field == "agente" else ("fecha_evento" if field == "fecha" else "categoria"),
                    "null_count": null_count,
                    "total_count": total,
                    "null_percentage": round((null_count / total * 100), 2) if total > 0 else 0,
                    "strategy_applied": "Inferido (Regla Regex)" if field == "agente" else "Conservar si no es critico",
                })
    return matrix


def get_critical_null_count():
    clauses = " OR ".join([f"{column} IS NULL" for column in CRITICAL_COLUMNS])
    with db_connector.engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM staging.stg_actividad_agente_ia WHERE {clauses}")).scalar() or 0


def get_dedup_report():
    """Reporta duplicados reales segun la misma clave compuesta usada en Staging."""
    candidate_df = build_candidate_staging_frame()
    if candidate_df.empty:
        return []

    grouped = (
        candidate_df
        .groupby(DEDUP_KEY, dropna=False)
        .size()
        .reset_index(name="count")
    )
    duplicates = grouped[grouped["count"] > 1]
    detected_by_source = duplicates.groupby("fuente")["count"].sum().to_dict()
    removed_by_source = duplicates.assign(removed=duplicates["count"] - 1).groupby("fuente")["removed"].sum().to_dict()
    candidate_by_source = candidate_df.groupby("fuente").size().to_dict()

    report = []
    for source, total in sorted(candidate_by_source.items()):
        removed = int(removed_by_source.get(source, 0))
        detected = int(detected_by_source.get(source, 0))
        report.append({
            "source": source,
            "total_detected": detected,
            "total_removed": removed,
            "total_kept": int(total - removed),
        })
    return report


def get_quality_issue_breakdown():
    """Desagrega la diferencia Raw/Staging por categorias defendibles."""
    candidate_df = build_candidate_staging_frame()
    with db_connector.engine.connect() as conn:
        raw_total = conn.execute(text("SELECT COUNT(*) FROM raw.raw_records")).scalar() or 0
        staging_total = conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia")).scalar() or 0
        http_errors = conn.execute(text("SELECT COUNT(*) FROM audit.pipeline_errors WHERE error_type ILIKE '%HTTP%' OR description ILIKE '%429%' OR description ILIKE '%403%'")).scalar() or 0
        survey_provisioned = conn.execute(text("SELECT COUNT(*) FROM raw.raw_records r JOIN raw.raw_files f ON r.file_id = f.id WHERE f.fuente = 'fuente_propia'")).scalar() or 0

    duplicate_real = int(candidate_df.duplicated(subset=DEDUP_KEY, keep="first").sum()) if not candidate_df.empty else 0
    critical_nulls = get_critical_null_count()
    unmapped = get_unmapped_agent_count()
    casting_errors = get_casting_report()
    casting_total = sum(item["failed_conversions"] for item in casting_errors)
    non_consolidated = max(raw_total - staging_total, 0)
    conflicts_or_existing = max(non_consolidated - duplicate_real - critical_nulls, 0)

    return [
        {
            "metric_name": "raw_records",
            "metric_value": raw_total,
            "evidence_basis": "COUNT(*) FROM raw.raw_records",
            "academic_interpretation": "Universo Raw cargado en PostgreSQL.",
        },
        {
            "metric_name": "staging_records",
            "metric_value": staging_total,
            "evidence_basis": "COUNT(*) FROM staging.stg_actividad_agente_ia",
            "academic_interpretation": "Registros consolidados en el contrato Staging.",
        },
        {
            "metric_name": "real_duplicate_records_removed",
            "metric_value": duplicate_real,
            "evidence_basis": "Clave compuesta fuente/plataforma/id/agente/fecha sobre candidatos Staging.",
            "academic_interpretation": "Duplicados reales detectados por la regla de deduplicacion.",
        },
        {
            "metric_name": "key_conflicts_or_preexisting_records",
            "metric_value": conflicts_or_existing,
            "evidence_basis": "Diferencia Raw-Staging no explicada por duplicados o nulos criticos.",
            "academic_interpretation": "Registros no insertados por conflicto de clave, carga previa o consolidacion historica.",
        },
        {
            "metric_name": "http_errors_logged",
            "metric_value": http_errors,
            "evidence_basis": "audit.pipeline_errors con errores HTTP/rate limit.",
            "academic_interpretation": "Fallos de extraccion documentados, no tratados como exitos.",
        },
        {
            "metric_name": "unmapped_agent_records",
            "metric_value": unmapped,
            "evidence_basis": "nombre_agente = 'Otro Agente IA' en Staging.",
            "academic_interpretation": "Registros validos, pero no homologados a un agente conocido.",
        },
        {
            "metric_name": "critical_null_records",
            "metric_value": critical_nulls,
            "evidence_basis": "Nulos en columnas criticas de Staging.",
            "academic_interpretation": "Registros con incumplimiento estructural critico.",
        },
        {
            "metric_name": "casting_or_transformation_errors",
            "metric_value": casting_total,
            "evidence_basis": "Conversion numerica sobre columnas metricas del candidato Staging.",
            "academic_interpretation": "Valores no convertibles durante transformacion.",
        },
        {
            "metric_name": "upse_survey_provisioned_records",
            "metric_value": survey_provisioned,
            "evidence_basis": "COUNT(*) Raw para fuente_propia.",
            "academic_interpretation": "Encuesta UPSE provisionada; pendiente de tabulacion academica final.",
        },
    ]


def get_unmapped_agent_count():
    with db_connector.engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia WHERE nombre_agente = 'Otro Agente IA'")).scalar() or 0


def get_casting_report():
    candidate_df = build_candidate_staging_frame()
    report = []
    if candidate_df.empty:
        return report

    for source, source_df in candidate_df.groupby("fuente"):
        for column in NUMERIC_COLUMNS:
            if column not in source_df.columns:
                continue
            series = source_df[column].dropna()
            if series.empty:
                failed = 0
                before = ""
            else:
                converted = pd.to_numeric(series, errors="coerce")
                failed_mask = converted.isna() & series.notna()
                failed = int(failed_mask.sum())
                before = str(series[failed_mask].iloc[0]) if failed > 0 else ""
            report.append({
                "source": source,
                "field_name": column,
                "target_type": "numeric",
                "failed_conversions": failed,
                "example_before": before,
                "example_after": "" if failed else "conversion_ok",
            })
    return report


def get_staging_contract_report():
    query = text("""
        SELECT ordinal_position, column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'staging'
          AND table_name = 'stg_actividad_agente_ia'
        ORDER BY ordinal_position
    """)
    with db_connector.engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    report = []
    for row in rows:
        column_name = row["column_name"]
        if column_name == "id":
            role = "technical_surrogate_key"
        elif column_name == "fecha_carga":
            role = "technical_audit_column"
        else:
            role = "analytical_contract_column"
        report.append({**dict(row), "contract_role": role})
    return report


def get_homologation_map():
    """Retorna el mapa conceptual de homologacion de las fuentes principales."""
    return [
        {"source": "github", "source_field": "stargazers_count", "staging_field": "stars_github", "transformation_rule": "Mapeo directo Integer"},
        {"source": "github", "source_field": "created_at", "staging_field": "fecha_evento", "transformation_rule": "Parse ISO Date a YYYY-MM-DD"},
        {"source": "hackernews", "source_field": "points", "staging_field": "cantidad_interacciones", "transformation_rule": "Mapeo directo Integer"},
        {"source": "hackernews", "source_field": "num_comments", "staging_field": "cantidad_menciones", "transformation_rule": "Mapeo directo Integer"},
        {"source": "devto", "source_field": "title/url/created_at", "staging_field": "titulo/url/fecha_evento", "transformation_rule": "Parse HTML con BeautifulSoup y normalizacion generica"},
        {"source": "reddit", "source_field": "title/url/created_at", "staging_field": "titulo/url/fecha_evento", "transformation_rule": "Scraping Playwright y normalizacion generica"},
        {"source": "google_trends", "source_field": "valor", "staging_field": "score_popularidad", "transformation_rule": "Mapeo numerico Float"},
        {"source": "fuente_propia", "source_field": "encuesta_upse", "staging_field": "pendiente", "transformation_rule": "Fuente provisionada; no tabulada como fuente academica final"},
    ]
