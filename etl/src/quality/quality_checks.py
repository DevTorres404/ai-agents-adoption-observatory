from functools import lru_cache

import pandas as pd
from sqlalchemy import text

from src.staging.stg_agents import extract_agent
from src.staging.stg_categories import assign_categories
from src.staging.stg_dates import parse_dates
from src.staging.stg_normalize_columns import normalize_dataframe
from src.staging.stg_semantic_dimensions import enrich_semantic_dimensions
from src.staging.stg_dedup import DEDUP_KEY, deduplication_stats
from src.quality.governance import reconcile_quality_counts
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
    "dim_nombre_plataforma",
    "dim_tipo_plataforma",
    "dim_ecosistema",
    "dim_plataforma_metodo",
    "dim_nombre_tecnologia",
    "dim_categoria_tecnologia",
    "dim_dominio_tecnologico",
    "dim_tipo_senal",
    "dim_tecnologia_metodo",
    "dim_nombre_comunidad",
    "dim_tipo_comunidad",
    "dim_region_comunidad",
    "dim_comunidad_metodo",
    "raw_file_id",
    "raw_record_id",
]

CRITICAL_COLUMNS = [
    "id_origen_registro", "fuente", "plataforma", "fecha_evento",
    "nombre_agente", "categoria", "dim_nombre_plataforma",
    "dim_nombre_tecnologia", "dim_nombre_comunidad",
]
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


def _fetch_raw_rows(run_id=None):
    query = text("""
        SELECT r.id AS raw_record_id, r.raw_data, f.fuente, f.tipo_fuente, f.id AS file_id,
               f.fecha_carga AS file_load_date
        FROM raw.raw_records r
        JOIN raw.raw_files f ON r.file_id = f.id
        WHERE (:run_id IS NULL OR COALESCE(r.run_id, f.run_id) = :run_id)
    """)
    with db_connector.engine.connect() as conn:
        return conn.execute(query, {"run_id": run_id}).fetchall()


@lru_cache(maxsize=16)
def build_candidate_staging_frame(run_id=None):
    """Construye una vez por ejecución el candidato usado por todos los reportes."""
    rows = _fetch_raw_rows(run_id)
    if not rows:
        return pd.DataFrame(columns=STAGING_CONTRACT_COLUMNS)

    grouped = {}
    for row in rows:
        key = (row.fuente, row.tipo_fuente, row.file_id, row.file_load_date)
        grouped.setdefault(key, []).append((row.raw_record_id, row.raw_data))

    frames = []
    for (fuente, tipo_fuente, file_id, file_load_date), records in grouped.items():
        raw_record_ids, raw_payloads = zip(*records)
        raw_df = pd.DataFrame(raw_payloads)
        meta = {
            "fuente": fuente,
            "tipo_fuente": tipo_fuente,
            "id": file_id,
            "fecha_carga": file_load_date,
        }
        normalized = normalize_dataframe(raw_df, meta)
        normalized["raw_record_id"] = list(raw_record_ids)
        frames.append(normalized)

    df = pd.concat(frames, ignore_index=True)
    df = parse_dates(df)
    df = extract_agent(df)
    df = assign_categories(df)
    df = enrich_semantic_dimensions(df)

    for col in DEDUP_KEY:
        if col in df.columns:
            df[col] = df[col].fillna("N/A").astype(str)

    return df


def get_overall_metrics(run_id=None):
    """Reconcile only rows associated with this run's immutable Raw snapshot."""
    with db_connector.engine.connect() as conn:
        raw_total = conn.execute(text("""
            SELECT COUNT(*) FROM raw.raw_records r
            JOIN raw.raw_files f ON f.id = r.file_id
            WHERE (:run_id IS NULL OR COALESCE(r.run_id, f.run_id) = :run_id)
        """), {"run_id": run_id}).scalar() or 0
        staging_total = conn.execute(text("""
            SELECT COUNT(*) FROM staging.stg_actividad_agente_ia s
            LEFT JOIN raw.raw_files f ON f.id = s.raw_file_id
            WHERE (:run_id IS NULL OR f.run_id = :run_id)
        """), {"run_id": run_id}).scalar() or 0

    candidate_df = build_candidate_staging_frame(run_id)
    eligible_df = candidate_df[candidate_df["nombre_agente"] != "Otro Agente IA"] if not candidate_df.empty else candidate_df
    _, duplicate_count = deduplication_stats(eligible_df) if not eligible_df.empty else (eligible_df, 0)
    metrics = reconcile_quality_counts(raw_total, len(eligible_df), duplicate_count, staging_total)
    metrics["total_nulls_removed"] = get_critical_null_count(run_id)
    return metrics


def get_nulls_matrix(run_id=None):
    """Analiza nulos por fuente y campo clave en Staging."""
    query = text("""
        SELECT
            s.fuente,
            COUNT(*) AS total_count,
            SUM(CASE WHEN nombre_agente IS NULL THEN 1 ELSE 0 END) AS null_agente,
            SUM(CASE WHEN fecha_evento IS NULL THEN 1 ELSE 0 END) AS null_fecha,
            SUM(CASE WHEN categoria IS NULL THEN 1 ELSE 0 END) AS null_categoria
        FROM staging.stg_actividad_agente_ia s
        LEFT JOIN raw.raw_files f ON f.id = s.raw_file_id
        WHERE (:run_id IS NULL OR f.run_id = :run_id)
        GROUP BY s.fuente
    """)

    matrix = []
    with db_connector.engine.connect() as conn:
        results = conn.execute(query, {"run_id": run_id}).fetchall()
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


def get_critical_null_count(run_id=None):
    clauses = " OR ".join([f"s.{column} IS NULL" for column in CRITICAL_COLUMNS])
    with db_connector.engine.connect() as conn:
        return conn.execute(text(f"""
            SELECT COUNT(*) FROM staging.stg_actividad_agente_ia s
            LEFT JOIN raw.raw_files f ON f.id = s.raw_file_id
            WHERE (:run_id IS NULL OR f.run_id = :run_id) AND ({clauses})
        """), {"run_id": run_id}).scalar() or 0


def get_dedup_report(run_id=None):
    """Reporta duplicados reales segun la misma clave compuesta usada en Staging."""
    candidate_df = build_candidate_staging_frame(run_id)
    if candidate_df.empty:
        return []
    candidate_df = candidate_df[candidate_df["nombre_agente"] != "Otro Agente IA"]

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
        survey_records = conn.execute(text("SELECT COUNT(*) FROM raw.raw_records r JOIN raw.raw_files f ON r.file_id = f.id WHERE f.fuente = 'fuente_propia'")).scalar() or 0

    _, duplicate_real = deduplication_stats(candidate_df) if not candidate_df.empty else (candidate_df, 0)
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
            "metric_name": "google_forms_survey_records",
            "metric_value": survey_records,
            "evidence_basis": "COUNT(*) Raw para fuente_propia.",
            "academic_interpretation": "Encuesta Google Forms consolidada como fuente propia academica.",
        },
    ]


def get_unmapped_agent_count():
    with db_connector.engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM staging.stg_actividad_agente_ia WHERE nombre_agente = 'Otro Agente IA'")).scalar() or 0


def get_casting_report(run_id=None):
    candidate_df = build_candidate_staging_frame(run_id)
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
        {"source": "fuente_propia", "source_field": "encuesta.json / Google Forms", "staging_field": "adopcion_academica", "transformation_rule": "Respuestas reales normalizadas a fuente propia academica"},
    ]
