DEDUP_KEY = ["fuente", "plataforma", "id_origen_registro", "nombre_agente"]
DEDUP_PREFERENCE = ["fecha_evento", "raw_file_id", "raw_record_id"]


def deduplicate_staging(df):
    """
    Deduplica filas basadas en la clave compuesta:
    fuente + plataforma + id_origen_registro + nombre_agente.

    Devuelve un DataFrame limpio y el conteo de filas descartadas.
    """
    total_inicial = len(df)
    df = df.copy()

    # La fecha describe cuándo ocurrió la observación, pero no identifica a la
    # entidad de origen. Excluirla evita que una nueva instantánea del mismo
    # repositorio, publicación o respuesta sobreviva como un hecho adicional.
    for col in DEDUP_KEY:
        if col in df.columns:
            # Motivo: reemplazar nulos evita que la deduplicacion deje pasar duplicados por campos vacios.
            df[col] = df[col].fillna('N/A').astype(str)

    # Se conserva la versión más reciente. raw_record_id es el desempate final
    # estable cuando dos candidatos pertenecen al mismo archivo y fecha.
    orden = [*DEDUP_KEY]
    for col in DEDUP_PREFERENCE:
        if col not in df.columns:
            df[col] = 0 if col != "fecha_evento" else ""
        orden.append(col)
    df_ordenado = df.sort_values(orden, kind='mergesort', na_position='first')
    df_limpio = (
        df_ordenado
        .drop_duplicates(subset=DEDUP_KEY, keep='last')
        .sort_values(orden, kind='mergesort', na_position='first')
        .reset_index(drop=True)
    )
    descartados = total_inicial - len(df_limpio)

    return df_limpio, descartados


def deduplication_stats(df):
    """Returns the exact discarded count produced by the shared rule."""
    deduplicated, removed = deduplicate_staging(df)
    return deduplicated, int(removed)
