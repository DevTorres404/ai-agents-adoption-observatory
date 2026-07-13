import hashlib

import pandas as pd


def normalize_dataframe(df, file_meta):
    """
    Maps raw source fields into the Staging analytical contract.
    Each branch keeps source-specific logic explicit for auditability.
    """
    fuente = file_meta.get("fuente", "desconocido")
    stg_df = pd.DataFrame()

    if fuente == "github":
        # Motivo: GitHub mide adopcion tecnica por repositorios; stars y forks son senales publicas de uso/reutilizacion.
        stg_df["id_origen_registro"] = df["id"].astype(str) if "id" in df.columns else df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "github"
        stg_df["titulo"] = df.get("name", "")
        stg_df["texto"] = df.get("description", "")
        stg_df["url"] = df.get("html_url", "")
        stg_df["fecha_evento_raw"] = df.get("created_at", None)
        stg_df["stars_github"] = df.get("stargazers_count", 0)
        stg_df["forks_github"] = df.get("forks_count", 0)
        stg_df["issues_abiertos"] = df.get("open_issues_count", 0)
        
        # FIX: Un repositorio encontrado es una mención al agente. 
        # Sus estrellas van a 'stars_github', no se suman a interacciones para no destruir la escala del BI.
        stg_df["cantidad_menciones"] = 1
        stg_df["cantidad_interacciones"] = stg_df["issues_abiertos"]

    elif fuente == "devto":
        # Motivo: Dev.to aporta publicaciones técnicas; reactions y comments miden participación comunitaria.
        stg_df["id_origen_registro"] = df["id"].astype(str) if "id" in df.columns else df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "devto"
        stg_df["titulo"] = df.get("title", "")
        stg_df["texto"] = df.get("description", "")
        stg_df["url"] = df.get("url", "")
        stg_df["fecha_evento_raw"] = df.get("created_at", None)
        # reactions_count = positive_reactions en la API de Dev.to
        stg_df["cantidad_interacciones"] = pd.to_numeric(df.get("reactions_count", pd.Series(0, index=df.index)), errors="coerce").fillna(0).astype(int)
        stg_df["cantidad_menciones"] = pd.to_numeric(df.get("comments_count", pd.Series(0, index=df.index)), errors="coerce").fillna(0).astype(int)

    elif fuente == "hackernews":
        # Motivo: HackerNews representa discusion comunitaria; puntos y comentarios aproximan aceptacion e intensidad del debate.
        stg_df["id_origen_registro"] = df["id"].astype(str) if "id" in df.columns else df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "hackernews"
        stg_df["titulo"] = df.get("title", "")
        stg_df["texto"] = df.get("story_text", df.get("text", ""))
        stg_df["url"] = df.get("url", "")
        stg_df["fecha_evento_raw"] = df.get("created_at", None)
        # points = votos HN; num_comments = comentarios
        stg_df["cantidad_interacciones"] = pd.to_numeric(df.get("points", pd.Series(0, index=df.index)), errors="coerce").fillna(0).astype(int)
        stg_df["cantidad_menciones"] = pd.to_numeric(df.get("num_comments", pd.Series(0, index=df.index)), errors="coerce").fillna(0).astype(int)

    elif fuente == "google_trends":
        # Motivo: Trends aporta interes relativo de busqueda; por eso se conserva como score de popularidad.
        stg_df["id_origen_registro"] = df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "google_trends"
        stg_df["titulo"] = df.get("agente", "") + " Trend"
        stg_df["texto"] = "Tendencia de busqueda en Google Trends"
        stg_df["url"] = "https://trends.google.com/"
        stg_df["fecha_evento_raw"] = df.get("fecha", None)
        stg_df["score_popularidad"] = df.get("valor", 0)

    elif fuente == "catalogo":
        if "pull_requests_count" in df.columns:
            # Motivo: AIDev resume actividad real en repositorios; PRs, merges y contribuidores aproximan adopcion productiva.
            agent = first_existing(df, ["agent"], "Agente IA")
            repo = first_existing(df, ["full_name"], "")
            language = first_existing(df, ["language"], "")
            pr_count = pd.to_numeric(first_existing(df, ["pull_requests_count"], 0), errors="coerce").fillna(0)
            merged_count = pd.to_numeric(first_existing(df, ["merged_pull_requests"], 0), errors="coerce").fillna(0)
            contributors = pd.to_numeric(first_existing(df, ["unique_contributors"], 0), errors="coerce").fillna(0)

            stg_df["id_origen_registro"] = agent.astype(str) + ":" + repo.astype(str)
            stg_df["plataforma"] = "aidedev_ai_coding"
            stg_df["titulo"] = agent.astype(str) + " - " + repo.astype(str)
            stg_df["texto"] = (
                "dataset=AIDev Dataset: AI Coding"
                + "; language=" + language.astype(str)
                + "; pull_requests=" + pr_count.astype(int).astype(str)
                + "; merged_pull_requests=" + merged_count.astype(int).astype(str)
            )
            stg_df["url"] = first_existing(df, ["sample_pr_url", "repo_url"], "")
            stg_df["fecha_evento_raw"] = first_existing(df, ["last_activity", "first_activity"], None)
            stg_df["cantidad_menciones"] = pr_count.astype(int)
            stg_df["cantidad_interacciones"] = (pr_count + merged_count + contributors).astype(int)
            stg_df["score_popularidad"] = pd.to_numeric(first_existing(df, ["merge_rate"], 0), errors="coerce")
            stg_df["stars_github"] = pd.to_numeric(first_existing(df, ["stars"], 0), errors="coerce").fillna(0).astype(int)
            stg_df["forks_github"] = pd.to_numeric(first_existing(df, ["forks"], 0), errors="coerce").fillna(0).astype(int)
            max_pr = pr_count.max() if pr_count.max() else 1
            max_contributors = contributors.max() if contributors.max() else 1
            # Motivo: se normaliza a 0-100 para comparar repositorios de tamanos distintos sin perder escala relativa.
            stg_df["indice_adopcion"] = ((pr_count / max_pr) * 100).round(2)
            stg_df["indice_innovacion"] = ((contributors / max_contributors) * 100).round(2)
        else:
            # Motivo: el catalogo manual funciona como maestro descriptivo; no genera metricas de actividad por si solo.
            official_name = first_existing(df, ["nombre_oficial", "name", "title"], "Agente IA")
            stg_df["id_origen_registro"] = first_existing(df, ["id"], "").astype(str)
            stg_df["plataforma"] = "catalogo_manual"
            stg_df["titulo"] = official_name.astype(str)
            stg_df["texto"] = (
                "empresa=" + first_existing(df, ["empresa"], "").astype(str)
                + "; categoria=" + first_existing(df, ["categoria"], "").astype(str)
                + "; estado=" + first_existing(df, ["estado"], "").astype(str)
            )
            stg_df["url"] = ""
            stg_df["fecha_evento_raw"] = None

    elif fuente == "fuente_propia":
        # Motivo: la encuesta UPSE se modela como percepcion declarada; cada respuesta cuenta como mencion individual.
        herramienta = first_existing(df, ["herramienta_principal", "herramienta_favorita"], "Ninguna")
        usa_ia = first_existing(df, ["usa_agentes_ia", "usa_ia"], "No especificado")
        perfil = first_existing(df, ["perfil_participante"], "No especificado")
        frecuencia = first_existing(df, ["frecuencia_uso_ia"], "No especificado")
        actividad = first_existing(df, ["actividad_uso_ia"], "No especificado")
        barrera = first_existing(df, ["barrera_adopcion"], "No especificado")

        stg_df["id_origen_registro"] = df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "encuesta_upse"
        stg_df["titulo"] = "Encuesta UPSE - " + herramienta.astype(str)
        stg_df["texto"] = (
            "perfil=" + perfil.astype(str)
            + "; usa_ia=" + usa_ia.astype(str)
            + "; frecuencia=" + frecuencia.astype(str)
            + "; actividad=" + actividad.astype(str)
            + "; barrera=" + barrera.astype(str)
        )
        stg_df["url"] = ""
        stg_df["fecha_evento_raw"] = first_existing(df, ["timestamp_respuesta", "Marca temporal", "created_at"], None)
        stg_df["cantidad_menciones"] = 1
        # Motivo: 1.0/0.5/0.0 separa adopcion activa, prueba exploratoria y no adopcion.
        stg_df["indice_adopcion"] = usa_ia.astype(str).str.lower().map({
            "si": 1.0,
            "sí": 1.0,
            "los he probado, pero no los uso regularmente": 0.5,
            "los he probado pero no los uso regularmente": 0.5,
            "no": 0.0,
        })
        stg_df["score_popularidad"] = pd.to_numeric(
            first_existing(df, ["mejora_productividad"], None),
            errors="coerce",
        )

    elif fuente == "reddit":
        # Motivo: Reddit aporta discusión comunitaria; score y comentarios miden engagement real.
        stg_df["id_origen_registro"] = df["id"].astype(str) if "id" in df.columns else df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = "reddit"
        stg_df["titulo"] = df.get("title", "")
        stg_df["texto"] = df.get("selftext", df.get("text", ""))
        stg_df["url"] = df.get("url", "")
        stg_df["fecha_evento_raw"] = df.get("created_at", None)
        # score = upvotes netos; num_comments = comentarios
        stg_df["cantidad_interacciones"] = pd.to_numeric(
            df.get("score", df.get("upvotes", pd.Series(0, index=df.index))), errors="coerce"
        ).fillna(0).astype(int)
        stg_df["cantidad_menciones"] = pd.to_numeric(
            df.get("num_comments", df.get("comments", pd.Series(1, index=df.index))), errors="coerce"
        ).fillna(1).astype(int)  # mínimo 1: el propio post cuenta como mención

    else:
        # Motivo: el fallback evita perder fuentes nuevas; conserva campos genericos hasta crear una regla especifica.
        stg_df["id_origen_registro"] = df.apply(hash_fallback, axis=1)
        stg_df["plataforma"] = fuente
        stg_df["titulo"] = df.get("title", df.get("name", "Sin titulo"))
        stg_df["texto"] = df.get("text", df.get("description", ""))
        stg_df["url"] = df.get("url", df.get("link", ""))
        stg_df["fecha_evento_raw"] = df.get("created_at", df.get("date", None))

    stg_df["fuente"] = fuente
    stg_df["tipo_fuente"] = file_meta.get("tipo_fuente", "desconocido")
    stg_df["raw_file_id"] = file_meta["id"]

    numeric_cols = [
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

    zero_default_cols = [
        "cantidad_menciones",
        "cantidad_interacciones",
        "stars_github",
        "forks_github",
        "issues_abiertos",
        "releases",
    ]

    for col in numeric_cols:
        if col not in stg_df.columns:
            # Motivo: las columnas numericas obligatorias deben existir aunque una fuente no aporte esa metrica.
            stg_df[col] = 0 if col in zero_default_cols else None

    return stg_df


def hash_fallback(row):
    content = str(row.to_dict()).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def first_existing(df, columns, default):
    for column in columns:
        if column in df.columns:
            return df[column]
    return pd.Series([default] * len(df), index=df.index)
